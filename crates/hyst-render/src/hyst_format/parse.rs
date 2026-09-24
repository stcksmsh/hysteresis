//! Ported from `src/isf/parse-isf.ts`. Parses the real `.hyst` file format:
//! a `/*{ ... }*/` JSON header immediately followed by GLSL. Deliberately a
//! real subset (see `types.rs`'s module doc) — anything accepted renders for
//! real, anything unsupported is rejected with a specific reason.

use serde_json::Value;

use super::types::{
    IsfDocument, IsfInput, IsfParseError, IsfPass, IsfScriptOutputKind, ScriptOutputDefault,
    UNSUPPORTED_INPUT_TYPES,
};

const CURRENT_HYSTERESIS_VERSION: f64 = 1.0;
const KNOWN_RESOURCES: [&str; 1] = ["scope"];
const SUPPORTED_TYPES: [&str; 8] = [
    "float",
    "bool",
    "long",
    "color",
    "point2D",
    "hysteresisSignal",
    "resource",
    "scriptOutput",
];

pub fn parse_hyst(source: &str) -> Result<IsfDocument, IsfParseError> {
    let start = source.find("/*").ok_or_else(|| {
        IsfParseError::Parse(
            "No ISF header comment found (expected a leading /*{ ... }*/ block)".into(),
        )
    })?;
    let end = source[start + 2..]
        .find("*/")
        .map(|i| start + 2 + i)
        .ok_or_else(|| {
            IsfParseError::Parse("ISF header comment is not closed (missing */)".into())
        })?;

    let header_text = source[start + 2..end].trim();
    let body = source[end + 2..].to_string();

    let header: Value = serde_json::from_str(header_text)
        .map_err(|e| IsfParseError::Parse(format!("ISF header is not valid JSON: {e}")))?;
    let header = header
        .as_object()
        .ok_or_else(|| IsfParseError::Parse("ISF header is not a JSON object".into()))?;

    // HYSTERESIS_VERSION: absent = a plain stock-ISF-compatible file.
    let mut hysteresis_version: Option<f64> = None;
    if let Some(v) = header.get("HYSTERESIS_VERSION") {
        let version = v.as_f64();
        if version != Some(CURRENT_HYSTERESIS_VERSION) {
            return Err(IsfParseError::UnsupportedFeature(format!(
                "HYSTERESIS_VERSION {v} is not supported by this parser — only version {CURRENT_HYSTERESIS_VERSION} is known."
            )));
        }
        hysteresis_version = version;
    }

    let passes_raw = header.get("PASSES").and_then(Value::as_array);
    if let Some(passes_raw) = passes_raw {
        if passes_raw
            .iter()
            .any(|p| p.get("PERSISTENT").map(is_truthy).unwrap_or(false))
        {
            return Err(IsfParseError::UnsupportedFeature(
                "PERSISTENT pass buffers are not supported yet — this shader needs its own frame memory beyond a single fullscreen draw.".into(),
            ));
        }
    }

    let passes: Vec<IsfPass> = match passes_raw {
        Some(passes_raw) if passes_raw.len() > 1 => {
            if hysteresis_version.is_none() {
                return Err(IsfParseError::UnsupportedFeature(format!(
                    "Multi-pass ISF shaders are not supported yet (this shader declares {} PASSES) — only single-pass generators/filters work, unless HYSTERESIS_VERSION declares real Hysteresis-format multi-pass support.",
                    passes_raw.len()
                )));
            }
            passes_raw
                .iter()
                .enumerate()
                .map(|(i, p)| parse_pass(p, i))
                .collect::<Result<Vec<_>, _>>()?
        }
        _ => vec![IsfPass::Fullscreen {
            target: String::new(),
        }],
    };

    if let Some(imported) = header.get("IMPORTED").and_then(Value::as_object) {
        if !imported.is_empty() {
            return Err(IsfParseError::UnsupportedFeature(
                "IMPORTED images are not supported yet — this shader needs an asset it can't bring with it.".into(),
            ));
        }
    }

    let raw_script = header.get("HYSTERESIS_SCRIPT").and_then(Value::as_str);
    let mut hysteresis_script: Option<String> = None;
    if let Some(script) = raw_script {
        if !script.is_empty() {
            if hysteresis_version.is_none() {
                return Err(IsfParseError::UnsupportedFeature(
                    "HYSTERESIS_SCRIPT requires HYSTERESIS_VERSION to be declared — a scriptless shader never needs this field.".into(),
                ));
            }
            hysteresis_script = Some(script.to_string());
        }
    }

    let raw_inputs: Vec<&Value> = header
        .get("INPUTS")
        .and_then(Value::as_array)
        .map(|a| a.iter().collect())
        .unwrap_or_default();

    let unsupported: Vec<String> = raw_inputs
        .iter()
        .filter_map(|i| {
            let t = i.get("TYPE").and_then(Value::as_str)?;
            if UNSUPPORTED_INPUT_TYPES.contains(&t) {
                let name = i.get("NAME").and_then(Value::as_str).unwrap_or("");
                Some(format!("{name} ({t})"))
            } else {
                None
            }
        })
        .collect();
    if !unsupported.is_empty() {
        return Err(IsfParseError::UnsupportedFeature(format!(
            "Unsupported ISF input type(s): {} — only float/bool/long/color/point2D/hysteresisSignal/resource/scriptOutput inputs are supported.",
            unsupported.join(", ")
        )));
    }

    let inputs: Vec<IsfInput> = raw_inputs
        .iter()
        .filter(|i| {
            i.get("TYPE")
                .and_then(Value::as_str)
                .map(|t| SUPPORTED_TYPES.contains(&t))
                .unwrap_or(false)
        })
        .map(|i| parse_input(i))
        .collect::<Result<Vec<_>, _>>()?;

    if hysteresis_script.is_none() {
        let script_output_names: Vec<&str> = inputs
            .iter()
            .filter(|i| matches!(i, IsfInput::ScriptOutput { .. }))
            .map(|i| i.name())
            .collect();
        if !script_output_names.is_empty() {
            return Err(IsfParseError::Parse(format!(
                "Input(s) declare TYPE scriptOutput ({}) but no HYSTERESIS_SCRIPT is declared to produce their values.",
                script_output_names.join(", ")
            )));
        }
        let script_texture_targets: Vec<&str> = passes
            .iter()
            .filter_map(|p| match p {
                IsfPass::ScriptTexture { target, .. } => Some(target.as_str()),
                _ => None,
            })
            .collect();
        if !script_texture_targets.is_empty() {
            return Err(IsfParseError::Parse(format!(
                "PASSES declare KIND scriptTexture (target {}) but no HYSTERESIS_SCRIPT is declared to produce their data.",
                script_texture_targets.join(", ")
            )));
        }
    }

    for pass in &passes {
        if let IsfPass::LineTrace { points, width, .. } = pass {
            let points_input = inputs.iter().find(|i| i.name() == points);
            match points_input {
                Some(IsfInput::Resource { .. }) => {}
                _ => {
                    return Err(IsfParseError::Parse(format!(
                        "PASSES lineTrace pass's POINTS \"{points}\" does not match any declared TYPE resource input"
                    )))
                }
            }
            if let Some(width_name) = width {
                let width_input = inputs.iter().find(|i| i.name() == width_name);
                match width_input {
                    Some(IsfInput::Float { .. }) | Some(IsfInput::HysteresisSignal { .. }) => {}
                    _ => {
                        return Err(IsfParseError::Parse(format!(
                            "PASSES lineTrace pass's WIDTH \"{width_name}\" does not match any declared TYPE float/hysteresisSignal input"
                        )))
                    }
                }
            }
        }
    }

    Ok(IsfDocument {
        description: header
            .get("DESCRIPTION")
            .and_then(Value::as_str)
            .map(String::from),
        credit: header
            .get("CREDIT")
            .and_then(Value::as_str)
            .map(String::from),
        categories: header
            .get("CATEGORIES")
            .and_then(Value::as_array)
            .map(|a| {
                a.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default(),
        inputs,
        hysteresis_version,
        passes,
        hysteresis_script,
        body,
    })
}

fn parse_pass(raw: &Value, index: usize) -> Result<IsfPass, IsfParseError> {
    let obj = raw
        .as_object()
        .ok_or_else(|| IsfParseError::Parse(format!("PASSES[{index}] is not an object")))?;
    let kind = obj
        .get("KIND")
        .and_then(Value::as_str)
        .unwrap_or("fullscreen");
    let target = obj
        .get("TARGET")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();

    match kind {
        "fullscreen" => Ok(IsfPass::Fullscreen { target }),
        "lineTrace" => {
            let points = obj.get("POINTS").and_then(Value::as_str).unwrap_or("").to_string();
            if points.is_empty() {
                return Err(IsfParseError::Parse(format!(
                    "PASSES[{index}] (lineTrace) is missing POINTS (the NAME of a declared TYPE resource input)"
                )));
            }
            if target.is_empty() {
                return Err(IsfParseError::Parse(format!(
                    "PASSES[{index}] (lineTrace) is missing TARGET (the name later passes will sample it by)"
                )));
            }
            let width = obj.get("WIDTH").and_then(Value::as_str).map(String::from);
            Ok(IsfPass::LineTrace { target, points, width })
        }
        "scriptTexture" => {
            let source = obj.get("SOURCE").and_then(Value::as_str).unwrap_or("").to_string();
            if source.is_empty() {
                return Err(IsfParseError::Parse(format!(
                    "PASSES[{index}] (scriptTexture) is missing SOURCE (the name of a field in the script's per-frame textures output)"
                )));
            }
            if target.is_empty() {
                return Err(IsfParseError::Parse(format!(
                    "PASSES[{index}] (scriptTexture) is missing TARGET (the name later passes will sample it by)"
                )));
            }
            let length = obj
                .get("LENGTH")
                .and_then(Value::as_u64)
                .filter(|&l| l > 0)
                .map(|l| l as u32);
            let length = length.ok_or_else(|| {
                IsfParseError::Parse(format!(
                    "PASSES[{index}] (scriptTexture) is missing a positive integer LENGTH (the fixed texel count)"
                ))
            })?;
            Ok(IsfPass::ScriptTexture { target, source, length })
        }
        other => Err(IsfParseError::UnsupportedFeature(format!(
            "PASSES[{index}] has unknown KIND \"{other}\" — only \"fullscreen\"/\"lineTrace\"/\"scriptTexture\" are supported."
        ))),
    }
}

fn parse_input(raw: &Value) -> Result<IsfInput, IsfParseError> {
    let name = raw
        .get("NAME")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    if name.is_empty() {
        return Err(IsfParseError::Parse("An ISF input is missing NAME".into()));
    }
    let label = raw.get("LABEL").and_then(Value::as_str).map(String::from);
    let ty = raw.get("TYPE").and_then(Value::as_str).unwrap_or("");

    match ty {
        "float" => Ok(IsfInput::Float {
            name,
            label,
            default: number_or(raw.get("DEFAULT"), 0.0),
            min: number_or(raw.get("MIN"), 0.0),
            max: number_or(raw.get("MAX"), 1.0),
        }),
        "bool" => Ok(IsfInput::Bool {
            name,
            label,
            default: raw.get("DEFAULT").and_then(Value::as_bool).unwrap_or(false),
        }),
        "long" => {
            let values: Vec<f64> = raw
                .get("VALUES")
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(Value::as_f64).collect())
                .unwrap_or_default();
            let labels: Vec<String> = raw
                .get("LABELS")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_else(|| values.iter().map(|v| v.to_string()).collect());
            let default = number_or(raw.get("DEFAULT"), values.first().copied().unwrap_or(0.0));
            Ok(IsfInput::Long {
                name,
                label,
                default,
                values,
                labels,
            })
        }
        "color" => {
            let d = color_array_or(raw.get("DEFAULT"), [1.0, 1.0, 1.0, 1.0]);
            Ok(IsfInput::Color {
                name,
                label,
                default: d,
            })
        }
        "hysteresisSignal" => {
            let signal = raw
                .get("SIGNAL")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if !hyst_core::ROUTABLE_SIGNAL_NAMES.contains(&signal.as_str()) {
                return Err(IsfParseError::Parse(format!(
                    "ISF input \"{name}\" declares TYPE hysteresisSignal with an unknown SIGNAL \"{signal}\" — must be one of: {}",
                    hyst_core::ROUTABLE_SIGNAL_NAMES.join(", ")
                )));
            }
            Ok(IsfInput::HysteresisSignal {
                name,
                label,
                signal,
                default: number_or(raw.get("DEFAULT"), 0.0),
            })
        }
        "resource" => {
            let resource = raw
                .get("RESOURCE")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if !KNOWN_RESOURCES.contains(&resource.as_str()) {
                return Err(IsfParseError::Parse(format!(
                    "ISF input \"{name}\" declares TYPE resource with an unknown RESOURCE \"{resource}\" — must be one of: {}",
                    KNOWN_RESOURCES.join(", ")
                )));
            }
            Ok(IsfInput::Resource {
                name,
                label,
                resource,
            })
        }
        "scriptOutput" => {
            let kind_str = raw.get("KIND").and_then(Value::as_str).unwrap_or("");
            let kind = match kind_str {
                "float" => IsfScriptOutputKind::Float,
                "bool" => IsfScriptOutputKind::Bool,
                "point2D" => IsfScriptOutputKind::Point2d,
                "color" => IsfScriptOutputKind::Color,
                _ => {
                    return Err(IsfParseError::Parse(format!(
                        "ISF input \"{name}\" declares TYPE scriptOutput with an unknown KIND \"{kind_str}\" — must be one of: float, bool, point2D, color"
                    )))
                }
            };
            let default = match kind {
                IsfScriptOutputKind::Float => {
                    ScriptOutputDefault::Float(number_or(raw.get("DEFAULT"), 0.0))
                }
                IsfScriptOutputKind::Bool => ScriptOutputDefault::Bool(
                    raw.get("DEFAULT").and_then(Value::as_bool).unwrap_or(false),
                ),
                IsfScriptOutputKind::Point2d => {
                    ScriptOutputDefault::Point2d(point2_array_or(raw.get("DEFAULT"), [0.0, 0.0]))
                }
                IsfScriptOutputKind::Color => ScriptOutputDefault::Color(color_array_or(
                    raw.get("DEFAULT"),
                    [1.0, 1.0, 1.0, 1.0],
                )),
            };
            Ok(IsfInput::ScriptOutput {
                name,
                label,
                kind,
                default,
            })
        }
        "point2D" => Ok(IsfInput::Point2d {
            name,
            label,
            default: point2_array_or(raw.get("DEFAULT"), [0.0, 0.0]),
            min: point2_array_or(raw.get("MIN"), [0.0, 0.0]),
            max: point2_array_or(raw.get("MAX"), [1.0, 1.0]),
        }),
        other => Err(IsfParseError::Parse(format!(
            "Unknown ISF input type: {other}"
        ))),
    }
}

/// JS-truthiness for a JSON value (matches the TS original's `(p).PERSISTENT`
/// bare-truthy check): only `null`, `false`, `0`, and `""` are falsy.
fn is_truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().map(|f| f != 0.0).unwrap_or(true),
        Value::String(s) => !s.is_empty(),
        Value::Array(_) | Value::Object(_) => true,
    }
}

fn number_or(v: Option<&Value>, fallback: f64) -> f64 {
    v.and_then(Value::as_f64)
        .filter(|n| n.is_finite())
        .unwrap_or(fallback)
}

fn point2_array_or(v: Option<&Value>, fallback: [f64; 2]) -> [f64; 2] {
    let Some(arr) = v.and_then(Value::as_array) else {
        return fallback;
    };
    [
        arr.first().and_then(Value::as_f64).unwrap_or(fallback[0]),
        arr.get(1).and_then(Value::as_f64).unwrap_or(fallback[1]),
    ]
}

fn color_array_or(v: Option<&Value>, fallback: [f64; 4]) -> [f64; 4] {
    let Some(arr) = v.and_then(Value::as_array) else {
        return fallback;
    };
    [
        arr.first().and_then(Value::as_f64).unwrap_or(fallback[0]),
        arr.get(1).and_then(Value::as_f64).unwrap_or(fallback[1]),
        arr.get(2).and_then(Value::as_f64).unwrap_or(fallback[2]),
        arr.get(3).and_then(Value::as_f64).unwrap_or(fallback[3]),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hyst_format::types::IsfPass;

    // Mirrors tests/unit/parse-isf.spec.ts's PLASMA_SRC fixture exactly —
    // a real-shaped ISF generator, not a synthetic minimal one.
    const PLASMA_SRC: &str = r#"/*{
  "DESCRIPTION": "simple plasma",
  "CREDIT": "test fixture",
  "CATEGORIES": ["Generator"],
  "INPUTS": [
    { "NAME": "speed", "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0, "MAX": 4.0 },
    { "NAME": "invert", "TYPE": "bool", "DEFAULT": false },
    { "NAME": "paletteIndex", "TYPE": "long", "DEFAULT": 1, "VALUES": [0, 1, 2], "LABELS": ["fire", "ice", "mono"] },
    { "NAME": "tint", "TYPE": "color", "DEFAULT": [1.0, 0.5, 0.2, 1.0] },
    { "NAME": "center", "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] }
  ]
}*/

void main() {
  vec2 uv = isf_FragNormCoord.xy;
  float v = sin((uv.x + center.x) * 10.0 + TIME * speed);
  gl_FragColor = vec4(tint.rgb * v, 1.0);
}
"#;

    #[test]
    fn parses_a_real_shaped_single_pass_generator_end_to_end() {
        let doc = parse_hyst(PLASMA_SRC).unwrap();
        assert_eq!(doc.description.as_deref(), Some("simple plasma"));
        assert_eq!(doc.categories, vec!["Generator".to_string()]);
        assert_eq!(doc.inputs.len(), 5);
        assert!(doc.body.contains("void main()"));
        assert!(doc.body.contains("gl_FragColor"));
    }

    #[test]
    fn parses_each_supported_input_type_with_its_real_fields() {
        let doc = parse_hyst(PLASMA_SRC).unwrap();
        let find = |name: &str| doc.inputs.iter().find(|i| i.name() == name).unwrap();

        assert_eq!(
            find("speed"),
            &IsfInput::Float {
                name: "speed".into(),
                label: None,
                default: 1.0,
                min: 0.0,
                max: 4.0
            }
        );
        assert_eq!(
            find("invert"),
            &IsfInput::Bool {
                name: "invert".into(),
                label: None,
                default: false
            }
        );
        assert_eq!(
            find("paletteIndex"),
            &IsfInput::Long {
                name: "paletteIndex".into(),
                label: None,
                default: 1.0,
                values: vec![0.0, 1.0, 2.0],
                labels: vec!["fire".into(), "ice".into(), "mono".into()],
            }
        );
        assert_eq!(
            find("tint"),
            &IsfInput::Color {
                name: "tint".into(),
                label: None,
                default: [1.0, 0.5, 0.2, 1.0]
            }
        );
        assert_eq!(
            find("center"),
            &IsfInput::Point2d {
                name: "center".into(),
                label: None,
                default: [0.5, 0.5],
                min: [0.0, 0.0],
                max: [1.0, 1.0],
            }
        );
    }

    #[test]
    fn rejects_a_missing_header_comment() {
        assert!(parse_hyst("void main() { gl_FragColor = vec4(1.0); }").is_err());
    }

    #[test]
    fn rejects_an_unclosed_header_comment() {
        assert!(parse_hyst(r#"/*{ "INPUTS": [] } void main() {}"#).is_err());
    }

    #[test]
    fn rejects_invalid_json_in_the_header() {
        assert!(parse_hyst("/*{ not json }*/ void main() {}").is_err());
    }

    #[test]
    fn rejects_an_image_input_with_a_specific_message() {
        let src = r#"/*{ "INPUTS": [ { "NAME": "srcImg", "TYPE": "image" } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let err = parse_hyst(src).unwrap_err();
        assert!(matches!(err, IsfParseError::UnsupportedFeature(_)));
        assert!(err.to_string().contains("srcImg (image)"));
    }

    #[test]
    fn rejects_an_audio_fft_input() {
        let src = r#"/*{ "INPUTS": [ { "NAME": "fft", "TYPE": "audioFFT" } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        assert!(matches!(
            parse_hyst(src),
            Err(IsfParseError::UnsupportedFeature(_))
        ));
    }

    #[test]
    fn rejects_a_multi_pass_shader_without_hysteresis_version() {
        let src = r#"/*{ "PASSES": [ {"TARGET":"a"}, {"TARGET":"b"} ], "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let err = parse_hyst(src).unwrap_err();
        assert!(matches!(err, IsfParseError::UnsupportedFeature(_)));
        assert!(err.to_string().contains("Multi-pass"));
    }

    #[test]
    fn rejects_a_persistent_buffer_pass() {
        let src = r#"/*{ "PASSES": [ {"TARGET":"buf","PERSISTENT":true} ], "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let err = parse_hyst(src).unwrap_err();
        assert!(err.to_string().contains("PERSISTENT"));
    }

    #[test]
    fn rejects_declared_imported_images() {
        let src = r#"/*{ "IMPORTED": { "logo": { "PATH": "logo.png" } }, "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        assert!(matches!(
            parse_hyst(src),
            Err(IsfParseError::UnsupportedFeature(_))
        ));
    }

    #[test]
    fn accepts_a_shader_with_no_inputs_at_all() {
        let src = r#"/*{ "DESCRIPTION": "flat color" }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let doc = parse_hyst(src).unwrap();
        assert!(doc.inputs.is_empty());
    }

    mod hysteresis_signal {
        use super::*;

        #[test]
        fn parses_a_valid_hysteresis_signal_input() {
            let src = r#"/*{ "INPUTS": [ { "NAME": "novelty", "TYPE": "hysteresisSignal", "SIGNAL": "noveltyLocal", "DEFAULT": 0.2 } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let doc = parse_hyst(src).unwrap();
            assert_eq!(
                doc.inputs,
                vec![IsfInput::HysteresisSignal {
                    name: "novelty".into(),
                    label: None,
                    signal: "noveltyLocal".into(),
                    default: 0.2,
                }]
            );
        }

        #[test]
        fn defaults_to_0_when_default_is_omitted() {
            let src = r#"/*{ "INPUTS": [ { "NAME": "fam", "TYPE": "hysteresisSignal", "SIGNAL": "familiarity" } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let doc = parse_hyst(src).unwrap();
            match &doc.inputs[0] {
                IsfInput::HysteresisSignal { default, .. } => assert_eq!(*default, 0.0),
                other => panic!("expected HysteresisSignal, got {other:?}"),
            }
        }

        #[test]
        fn rejects_an_unknown_signal_name_with_a_specific_message() {
            let src = r#"/*{ "INPUTS": [ { "NAME": "bad", "TYPE": "hysteresisSignal", "SIGNAL": "totallyMadeUp" } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(err
                .to_string()
                .contains(r#"unknown SIGNAL "totallyMadeUp""#));
        }

        #[test]
        fn rejects_a_missing_signal() {
            let src = r#"/*{ "INPUTS": [ { "NAME": "bad", "TYPE": "hysteresisSignal" } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            assert!(parse_hyst(src).is_err());
        }
    }

    #[test]
    fn rejects_a_declared_hysteresis_script_without_hysteresis_version() {
        let src = r#"/*{ "HYSTERESIS_SCRIPT": "function update() {}", "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let err = parse_hyst(src).unwrap_err();
        assert!(matches!(err, IsfParseError::UnsupportedFeature(_)));
        assert!(err.to_string().contains("HYSTERESIS_VERSION"));
    }

    #[test]
    fn parses_a_real_hysteresis_script_under_hysteresis_version() {
        let src = r#"/*{ "HYSTERESIS_VERSION": 1, "HYSTERESIS_SCRIPT": "function update() { return {}; }", "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let doc = parse_hyst(src).unwrap();
        assert_eq!(
            doc.hysteresis_script.as_deref(),
            Some("function update() { return {}; }")
        );
    }

    #[test]
    fn does_not_reject_a_shader_with_an_empty_absent_hysteresis_script() {
        let src = r#"/*{ "HYSTERESIS_SCRIPT": "", "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
        let doc = parse_hyst(src).unwrap();
        assert!(doc.hysteresis_script.is_none());
    }

    mod hysteresis_version_and_multi_pass {
        use super::*;

        #[test]
        fn a_plain_file_gets_the_implicit_single_fullscreen_pass() {
            let doc = parse_hyst(PLASMA_SRC).unwrap();
            assert!(doc.hysteresis_version.is_none());
            assert_eq!(
                doc.passes,
                vec![IsfPass::Fullscreen {
                    target: String::new()
                }]
            );
        }

        #[test]
        fn rejects_an_unrecognized_hysteresis_version() {
            let src = r#"/*{ "HYSTERESIS_VERSION": 99, "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(matches!(err, IsfParseError::UnsupportedFeature(_)));
            assert!(err.to_string().contains("HYSTERESIS_VERSION"));
        }

        #[test]
        fn a_stock_multi_pass_shader_without_version_is_still_rejected() {
            let src = r#"/*{ "PASSES": [ {"TARGET":"a"}, {"TARGET":"b"} ], "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            assert!(parse_hyst(src)
                .unwrap_err()
                .to_string()
                .contains("Multi-pass"));
        }

        #[test]
        fn parses_a_real_line_trace_plus_fullscreen_passes_pair() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "PASSES": [
                  { "TARGET": "beamTex", "KIND": "lineTrace", "POINTS": "scope", "WIDTH": "beamWidth" },
                  { "TARGET": "", "KIND": "fullscreen" }
                ],
                "INPUTS": [
                  { "NAME": "scope", "TYPE": "resource", "RESOURCE": "scope" },
                  { "NAME": "beamWidth", "TYPE": "float", "DEFAULT": 0.01, "MIN": 0.001, "MAX": 0.05 }
                ]
              }*/
              uniform sampler2D beamTex;
              void main() { gl_FragColor = texture2D(beamTex, isf_FragNormCoord); }"#;
            let doc = parse_hyst(src).unwrap();
            assert_eq!(doc.hysteresis_version, Some(1.0));
            assert_eq!(
                doc.passes,
                vec![
                    IsfPass::LineTrace {
                        target: "beamTex".into(),
                        points: "scope".into(),
                        width: Some("beamWidth".into()),
                    },
                    IsfPass::Fullscreen {
                        target: String::new()
                    },
                ]
            );
            assert!(doc.inputs.contains(&IsfInput::Resource {
                name: "scope".into(),
                label: None,
                resource: "scope".into(),
            }));
        }

        #[test]
        fn rejects_an_unknown_resource() {
            let src = r#"/*{ "HYSTERESIS_VERSION": 1, "INPUTS": [ { "NAME": "x", "TYPE": "resource", "RESOURCE": "madeUp" } ] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(err.to_string().contains(r#"unknown RESOURCE "madeUp""#));
        }

        #[test]
        fn rejects_a_line_trace_pass_with_an_unknown_kind() {
            let src = r#"/*{ "HYSTERESIS_VERSION": 1, "PASSES": [ {"TARGET":"a","KIND":"particles"}, {"TARGET":"","KIND":"fullscreen"} ], "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(matches!(err, IsfParseError::UnsupportedFeature(_)));
            assert!(err.to_string().contains(r#"unknown KIND "particles""#));
        }

        #[test]
        fn rejects_a_line_trace_pass_whose_points_does_not_match_a_declared_input() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "PASSES": [ { "TARGET": "beamTex", "KIND": "lineTrace", "POINTS": "nope" }, { "TARGET": "", "KIND": "fullscreen" } ],
                "INPUTS": []
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(err.to_string().contains(r#"POINTS "nope""#));
        }

        #[test]
        fn still_rejects_persistent_even_under_hysteresis_version() {
            let src = r#"/*{ "HYSTERESIS_VERSION": 1, "PASSES": [ {"TARGET":"buf","PERSISTENT":true} ], "INPUTS": [] }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            assert!(parse_hyst(src)
                .unwrap_err()
                .to_string()
                .contains("PERSISTENT"));
        }
    }

    mod script_output_and_script_texture {
        use super::*;

        #[test]
        fn parses_each_script_output_kind_with_its_real_default_shape() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "HYSTERESIS_SCRIPT": "function update() { return {}; }",
                "INPUTS": [
                  { "NAME": "zoom", "TYPE": "scriptOutput", "KIND": "float", "DEFAULT": 2.0 },
                  { "NAME": "flash", "TYPE": "scriptOutput", "KIND": "bool", "DEFAULT": false },
                  { "NAME": "c", "TYPE": "scriptOutput", "KIND": "point2D", "DEFAULT": [0.25, 0.0] },
                  { "NAME": "tint", "TYPE": "scriptOutput", "KIND": "color", "DEFAULT": [1, 1, 1, 1] }
                ]
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let doc = parse_hyst(src).unwrap();
            let find = |name: &str| doc.inputs.iter().find(|i| i.name() == name).unwrap();
            assert_eq!(
                find("zoom"),
                &IsfInput::ScriptOutput {
                    name: "zoom".into(),
                    label: None,
                    kind: IsfScriptOutputKind::Float,
                    default: ScriptOutputDefault::Float(2.0),
                }
            );
            assert_eq!(
                find("flash"),
                &IsfInput::ScriptOutput {
                    name: "flash".into(),
                    label: None,
                    kind: IsfScriptOutputKind::Bool,
                    default: ScriptOutputDefault::Bool(false),
                }
            );
            assert_eq!(
                find("c"),
                &IsfInput::ScriptOutput {
                    name: "c".into(),
                    label: None,
                    kind: IsfScriptOutputKind::Point2d,
                    default: ScriptOutputDefault::Point2d([0.25, 0.0]),
                }
            );
            assert_eq!(
                find("tint"),
                &IsfInput::ScriptOutput {
                    name: "tint".into(),
                    label: None,
                    kind: IsfScriptOutputKind::Color,
                    default: ScriptOutputDefault::Color([1.0, 1.0, 1.0, 1.0]),
                }
            );
        }

        #[test]
        fn rejects_a_script_output_input_with_an_unknown_kind() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "HYSTERESIS_SCRIPT": "function update() { return {}; }",
                "INPUTS": [ { "NAME": "x", "TYPE": "scriptOutput", "KIND": "long" } ]
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(err.to_string().contains(r#"unknown KIND "long""#));
        }

        #[test]
        fn rejects_a_script_output_input_with_no_hysteresis_script_declared() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "INPUTS": [ { "NAME": "x", "TYPE": "scriptOutput", "KIND": "float" } ]
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            let msg = err.to_string();
            assert!(msg.contains("scriptOutput") && msg.contains("no HYSTERESIS_SCRIPT"));
        }

        #[test]
        fn parses_a_real_script_texture_pass() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "HYSTERESIS_SCRIPT": "function update() { return {}; }",
                "PASSES": [
                  { "TARGET": "refOrbit", "KIND": "scriptTexture", "SOURCE": "refOrbit", "LENGTH": 192 },
                  { "TARGET": "", "KIND": "fullscreen" }
                ],
                "INPUTS": []
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let doc = parse_hyst(src).unwrap();
            assert_eq!(
                doc.passes,
                vec![
                    IsfPass::ScriptTexture {
                        target: "refOrbit".into(),
                        source: "refOrbit".into(),
                        length: 192
                    },
                    IsfPass::Fullscreen {
                        target: String::new()
                    },
                ]
            );
        }

        #[test]
        fn rejects_a_script_texture_pass_missing_a_positive_integer_length() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "HYSTERESIS_SCRIPT": "function update() { return {}; }",
                "PASSES": [ { "TARGET": "refOrbit", "KIND": "scriptTexture", "SOURCE": "refOrbit" }, { "TARGET": "", "KIND": "fullscreen" } ],
                "INPUTS": []
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            assert!(err.to_string().contains("LENGTH"));
        }

        #[test]
        fn rejects_a_script_texture_pass_with_no_hysteresis_script_declared() {
            let src = r#"/*{
                "HYSTERESIS_VERSION": 1,
                "PASSES": [ { "TARGET": "refOrbit", "KIND": "scriptTexture", "SOURCE": "refOrbit", "LENGTH": 192 }, { "TARGET": "", "KIND": "fullscreen" } ],
                "INPUTS": []
              }*/
void main() { gl_FragColor = vec4(1.0); }"#;
            let err = parse_hyst(src).unwrap_err();
            let msg = err.to_string();
            assert!(msg.contains("scriptTexture") && msg.contains("no HYSTERESIS_SCRIPT"));
        }

        #[test]
        fn a_scriptless_document_is_completely_unaffected() {
            let doc = parse_hyst(PLASMA_SRC).unwrap();
            assert!(doc.hysteresis_script.is_none());
            assert!(doc
                .inputs
                .iter()
                .all(|i| !matches!(i, IsfInput::ScriptOutput { .. })));
        }
    }
}

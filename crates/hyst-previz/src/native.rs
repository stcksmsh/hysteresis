//! CPU-only SVG arm inspection. Geometry is illustrative: 32/26/12 cm links.

use std::fmt::Write;

use hyst_output::ChoreographyFrame;

use crate::{Arm, Pose};

fn escape_xml(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for ch in text.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            c if c.is_control() => out.push(' '),
            c => out.push(c),
        }
    }
    out
}

/// Render one sampled score frame as a side-view planar-arm SVG.
/// This is a CPU inspection artifact, never a native window or hardware preview.
pub fn render_score_svg(frame: &ChoreographyFrame<'_>) -> String {
    const SCALE: f64 = 4.0;
    const ORIGIN_X: f64 = 180.0;
    const FLOOR_Y: f64 = 330.0;
    let pose = Pose(frame.joints_degrees.map(f64::to_radians));
    let points = Arm::default().joints(pose);
    let mapped: Vec<_> = points
        .iter()
        .map(|point| (ORIGIN_X + point.x * SCALE, FLOOR_Y - point.y * SCALE))
        .collect();
    let gesture = escape_xml(frame.gesture);
    let phase = escape_xml(frame.phase);
    let energy = frame.energy.clamp(0.0, 1.0) as f64;
    let accent = frame.accent.clamp(0.0, 1.0) as f64;
    let anchor = frame
        .arrival_anchor
        .map(|t| format!("{t:.3}s"))
        .unwrap_or_else(|| "none".into());
    let mut svg = String::with_capacity(2400);
    write!(svg, r##"<svg xmlns="http://www.w3.org/2000/svg" width="760" height="440" viewBox="0 0 760 440" role="img" aria-label="Simulated planar arm at {time:.3} seconds"><rect width="100%" height="100%" fill="#10151c"/><text x="28" y="38" fill="#e8edf3" font-family="monospace" font-size="18">SIMULATION — planar side view, 32/26/12 cm assumed</text><text x="28" y="68" fill="#aebdcb" font-family="monospace" font-size="15">t={time:.3}s  cue={cue}  gesture={gesture}  phase={phase}</text><line x1="30" y1="{FLOOR_Y}" x2="720" y2="{FLOOR_Y}" stroke="#4e5b68" stroke-width="2"/><text x="35" y="352" fill="#8291a0" font-family="monospace" font-size="13">baseline</text>"##, time = frame.time_seconds, cue = frame.cue_index, gesture = gesture, phase = phase).unwrap();
    for pair in mapped.windows(2) {
        write!(svg, r##"<line x1="{:.2}" y1="{:.2}" x2="{:.2}" y2="{:.2}" stroke="#7ed6df" stroke-width="10" stroke-linecap="round"/>"##, pair[0].0, pair[0].1, pair[1].0, pair[1].1).unwrap();
    }
    for (index, point) in mapped.iter().enumerate() {
        write!(svg, r##"<circle cx="{:.2}" cy="{:.2}" r="{}" fill="{}"/><text x="{:.2}" y="{:.2}" fill="#10151c" font-family="monospace" font-size="11" text-anchor="middle">{}</text>"##, point.0, point.1, if index == 0 { 12 } else { 9 }, if index == 0 { "#f6bd60" } else { "#f7f9fb" }, point.0, point.1 + 4.0, index).unwrap();
    }
    write!(svg, r##"<text x="470" y="130" fill="#e8edf3" font-family="monospace" font-size="15">joint degrees</text><text x="470" y="156" fill="#aebdcb" font-family="monospace" font-size="14">shoulder {q0:.2}°</text><text x="470" y="180" fill="#aebdcb" font-family="monospace" font-size="14">elbow    {q1:.2}°</text><text x="470" y="204" fill="#aebdcb" font-family="monospace" font-size="14">wrist    {q2:.2}°</text><text x="470" y="235" fill="#aebdcb" font-family="monospace" font-size="14">arrival {anchor}</text><text x="470" y="270" fill="#e8edf3" font-family="monospace" font-size="14">energy</text><rect x="540" y="257" width="150" height="16" fill="#273542"/><rect x="540" y="257" width="{energy_width:.2}" height="16" fill="#62c370"/><text x="470" y="302" fill="#e8edf3" font-family="monospace" font-size="14">accent</text><rect x="540" y="289" width="150" height="16" fill="#273542"/><rect x="540" y="289" width="{accent_width:.2}" height="16" fill="#f6bd60"/></svg>"##, q0 = frame.joints_degrees[0], q1 = frame.joints_degrees[1], q2 = frame.joints_degrees[2], anchor = anchor, energy_width = energy * 150.0, accent_width = accent * 150.0).unwrap();
    svg
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn svg_uses_fk_and_escapes_score_metadata() {
        let frame = ChoreographyFrame {
            time_seconds: 2.0,
            joints_degrees: [0.0, 0.0, 0.0],
            cue_index: 1,
            gesture: "<strike&>",
            phase: "\"arrival\"",
            energy: 0.5,
            accent: 0.25,
            arrival_anchor: Some(2.0),
        };
        let svg = render_score_svg(&frame);
        assert!(svg.contains("&lt;strike&amp;&gt;"));
        assert!(svg.contains("&quot;arrival&quot;"));
        // 32 + 26 + 12 cm, four SVG pixels per cm, shoulder at x=180.
        assert!(svg.contains("cx=\"460.00\" cy=\"330.00\""));
    }
}

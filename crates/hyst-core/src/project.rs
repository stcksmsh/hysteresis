//! Project format (implementation plan §0.6 / R0): a plain directory as the
//! working format (git-friendly, diffable) and `.hystproj` — a byte-faithful
//! zip of that same directory — for export/sharing. The loader accepts
//! either.
//!
//! No TS precedent exists for this (the browser package had no project
//! container at all — a track was just a URL the host supplied). Designed
//! fresh here, deliberately minimal: a `project.json` manifest at the root
//! naming the project and pointing at its audio/sidecar, plus whatever other
//! files (`.hyst` shaders, Lua scripts, more sidecars) live alongside it.
//! Nothing about the manifest shape is final — later workstreams (R2's
//! `.hyst` assets, R3's scripts, R7's choreography scores) will likely add
//! fields; keep any addition additive, per the sidecar schema's own
//! precedent.

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use walkdir::WalkDir;
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

use crate::error::{HystError, Result};

pub const MANIFEST_FILENAME: &str = "project.json";

/// The one file every project directory must have at its root.
#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectManifest {
    pub name: String,
    /// The *project format's* own version — distinct from the sidecar
    /// schema version, which each referenced sidecar file carries itself.
    pub format_version: u32,
    /// Relative path (from the project root) to the source audio, if any.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audio: Option<String>,
    /// Relative path (from the project root) to the primary sidecar, if any.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sidecar: Option<String>,
}

pub const PROJECT_FORMAT_VERSION: u32 = 1;

impl ProjectManifest {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            format_version: PROJECT_FORMAT_VERSION,
            audio: None,
            sidecar: None,
        }
    }
}

/// A loaded project: the manifest plus the directory it lives in. `root` is
/// always a plain directory on disk — `.hystproj` loading extracts to a
/// temp/target directory first, it never operates on the zip in place.
#[derive(Debug)]
pub struct Project {
    pub manifest: ProjectManifest,
    pub root: PathBuf,
}

impl Project {
    /// Load a project directory: read and validate `project.json` at its
    /// root. Does not eagerly validate that `audio`/`sidecar` paths exist —
    /// callers that need those files should open them and get a real io
    /// error naming the actual missing path, rather than this function
    /// guessing every field's importance.
    pub fn load_dir(root: impl AsRef<Path>) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let manifest_path = root.join(MANIFEST_FILENAME);
        let raw = fs::read_to_string(&manifest_path).map_err(|source| HystError::Io {
            path: manifest_path.clone(),
            source,
        })?;
        let manifest: ProjectManifest =
            serde_json::from_str(&raw).map_err(|source| HystError::Json {
                path: manifest_path.clone(),
                source,
            })?;
        if manifest.format_version > PROJECT_FORMAT_VERSION {
            return Err(HystError::InvalidProject {
                reason: format!(
                    "project.json declares format_version {}, this build only understands up to {}",
                    manifest.format_version, PROJECT_FORMAT_VERSION
                ),
            });
        }
        Ok(Self { manifest, root })
    }

    /// Export this project as a byte-faithful `.hystproj` zip: every file
    /// under `root` (walked recursively) is stored with its relative path
    /// and exact original bytes — no transformation, no line-ending
    /// normalization, no re-serialization of the manifest.
    pub fn export_zip(&self, dest: impl AsRef<Path>) -> Result<()> {
        let dest = dest.as_ref();
        let file = fs::File::create(dest).map_err(|source| HystError::Io {
            path: dest.to_path_buf(),
            source,
        })?;
        let mut writer = ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);

        for entry in WalkDir::new(&self.root).into_iter().filter_map(|e| e.ok()) {
            let path = entry.path();
            let rel = path
                .strip_prefix(&self.root)
                .expect("walkdir entries are always under root");
            if rel.as_os_str().is_empty() {
                continue; // the root itself
            }
            let rel_str = rel.to_string_lossy().replace('\\', "/");

            if entry.file_type().is_dir() {
                writer
                    .add_directory(format!("{rel_str}/"), options)
                    .map_err(HystError::from)?;
            } else if entry.file_type().is_file() {
                let bytes = fs::read(path).map_err(|source| HystError::Io {
                    path: path.to_path_buf(),
                    source,
                })?;
                writer
                    .start_file(rel_str, options)
                    .map_err(HystError::from)?;
                writer.write_all(&bytes).map_err(|source| HystError::Io {
                    path: path.to_path_buf(),
                    source,
                })?;
            }
        }
        writer.finish().map_err(HystError::from)?;
        Ok(())
    }

    /// Load a `.hystproj` by extracting it byte-faithfully into
    /// `extract_into` (created if it doesn't exist, must be empty), then
    /// loading it as a plain project directory.
    pub fn load_hystproj(
        archive_path: impl AsRef<Path>,
        extract_into: impl AsRef<Path>,
    ) -> Result<Self> {
        let archive_path = archive_path.as_ref();
        let extract_into = extract_into.as_ref();
        fs::create_dir_all(extract_into).map_err(|source| HystError::Io {
            path: extract_into.to_path_buf(),
            source,
        })?;

        let file = fs::File::open(archive_path).map_err(|source| HystError::Io {
            path: archive_path.to_path_buf(),
            source,
        })?;
        let mut archive = ZipArchive::new(file).map_err(HystError::from)?;

        for i in 0..archive.len() {
            let mut zip_entry = archive.by_index(i).map_err(HystError::from)?;
            let out_path = match zip_entry.enclosed_name() {
                Some(name) => extract_into.join(name),
                None => continue, // reject unsafe paths (path traversal etc.) silently skipped
            };

            if zip_entry.is_dir() {
                fs::create_dir_all(&out_path).map_err(|source| HystError::Io {
                    path: out_path.clone(),
                    source,
                })?;
            } else {
                if let Some(parent) = out_path.parent() {
                    fs::create_dir_all(parent).map_err(|source| HystError::Io {
                        path: parent.to_path_buf(),
                        source,
                    })?;
                }
                let mut buf = Vec::with_capacity(zip_entry.size() as usize);
                zip_entry
                    .read_to_end(&mut buf)
                    .map_err(|source| HystError::Io {
                        path: out_path.clone(),
                        source,
                    })?;
                fs::write(&out_path, &buf).map_err(|source| HystError::Io {
                    path: out_path.clone(),
                    source,
                })?;
            }
        }

        Self::load_dir(extract_into)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn write_sample_project(root: &Path) {
        fs::create_dir_all(root.join("shaders")).unwrap();
        let manifest = ProjectManifest {
            name: "Test Project".into(),
            format_version: PROJECT_FORMAT_VERSION,
            audio: Some("master.wav".into()),
            sidecar: Some("master.sidecar.json".into()),
        };
        fs::write(
            root.join(MANIFEST_FILENAME),
            serde_json::to_string_pretty(&manifest).unwrap(),
        )
        .unwrap();
        fs::write(root.join("master.wav"), [1u8, 2, 3, 4, 5]).unwrap();
        fs::write(root.join("master.sidecar.json"), "{}").unwrap();
        fs::write(root.join("shaders/example.hyst"), "// glsl placeholder\n").unwrap();
    }

    #[test]
    fn loads_a_plain_project_directory() {
        let dir = tempdir().unwrap();
        write_sample_project(dir.path());

        let project = Project::load_dir(dir.path()).unwrap();
        assert_eq!(project.manifest.name, "Test Project");
        assert_eq!(project.manifest.audio.as_deref(), Some("master.wav"));
    }

    #[test]
    fn rejects_a_directory_with_no_manifest() {
        let dir = tempdir().unwrap();
        assert!(Project::load_dir(dir.path()).is_err());
    }

    #[test]
    fn hystproj_export_and_reload_round_trips_byte_faithfully() {
        let src_dir = tempdir().unwrap();
        write_sample_project(src_dir.path());
        let original = Project::load_dir(src_dir.path()).unwrap();

        let zip_dir = tempdir().unwrap();
        let zip_path = zip_dir.path().join("test.hystproj");
        original.export_zip(&zip_path).unwrap();

        let extract_dir = tempdir().unwrap();
        let reloaded =
            Project::load_hystproj(&zip_path, extract_dir.path().join("extracted")).unwrap();

        assert_eq!(reloaded.manifest, original.manifest);

        // Byte-faithful: every non-manifest file's raw bytes match exactly.
        let original_wav = fs::read(src_dir.path().join("master.wav")).unwrap();
        let reloaded_wav = fs::read(reloaded.root.join("master.wav")).unwrap();
        assert_eq!(original_wav, reloaded_wav);

        let original_shader = fs::read(src_dir.path().join("shaders/example.hyst")).unwrap();
        let reloaded_shader = fs::read(reloaded.root.join("shaders/example.hyst")).unwrap();
        assert_eq!(original_shader, reloaded_shader);
    }
}

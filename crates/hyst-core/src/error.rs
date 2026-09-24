use std::path::PathBuf;

#[derive(Debug, thiserror::Error)]
pub enum HystError {
    #[error("io error at {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },

    #[error("invalid JSON in {path}: {source}")]
    Json {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },

    #[error("not a valid sidecar: {reason}")]
    InvalidSidecar { reason: String },

    #[error("not a valid project: {reason}")]
    InvalidProject { reason: String },

    #[error("zip archive error: {0}")]
    Zip(#[from] zip::result::ZipError),
}

pub type Result<T> = std::result::Result<T, HystError>;

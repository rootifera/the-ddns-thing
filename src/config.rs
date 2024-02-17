use std::fs::{self, File};
use std::io::{self, Write};
use std::path::Path;

fn check_file_exists(file_path: &Path, default_contents: &str) -> io::Result<()> {
    if !file_path.exists() {
        if let Some(parent) = file_path.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut file = File::create(file_path)?;
        file.write_all(default_contents.as_bytes())?;
    }
    Ok(())
}

pub fn check_and_create_config_files() -> io::Result<()> {
    let domains_cfg_path = Path::new("/etc/cfddnsthing/domains.cfg");
    let credentials_cfg_path = Path::new("/etc/cfddnsthing/credentials.cfg");

    check_file_exists(domains_cfg_path, "# Add your domains here. Please see README\n")?;
    check_file_exists(credentials_cfg_path, "# Add your credentials here. Please see README\n")?;

    Ok(())
}

/// I guess check credentials from env vars will come here
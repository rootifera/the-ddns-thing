use reqwest;
use regex::Regex;
use std::error::Error;

/// simple get public IP and check if it is valid stuff

async fn get_public_ip_from_url(url: &str) -> Result<String, Box<dyn Error>> {
    let response = reqwest::get(url).await?;
    let body = response.text().await?;
    let ip_regex = Regex::new(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")?;
    if ip_regex.is_match(&body.trim()) {
        Ok(body.trim().to_string())
    } else {
        Err("Invalid IP format received".into())
    }
}

pub async fn get_public_ip() -> Result<String, Box<dyn Error>> {
    let urls = [
        "http://checkip.amazonaws.com/",
        "http://icanhazip.com/",
        "http://ident.me/",
    ];

    for url in urls.iter() {
        match get_public_ip_from_url(url).await {
            Ok(ip) => return Ok(ip),
            Err(_) => continue,
        }
    }

    Err("Getting public IP failed, check your internet connection.".into())
}

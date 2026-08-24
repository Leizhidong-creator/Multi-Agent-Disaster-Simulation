from scripts.security_scan import run_git, scan_text


def test_git_output_uses_utf8_for_chinese_repository_content() -> None:
    readme = run_git("show", ":README.md")

    assert isinstance(readme, str)
    assert "智演 Agent" in readme


def test_detects_secret_without_echoing_value() -> None:
    secret = "sk-" + "A" * 32
    findings = scan_text("fixture.txt", f"LLM_API_KEY={secret}")

    assert findings[0].rule == "openai_compatible_key"
    assert secret not in findings[0].render()


def test_detects_private_key_and_personal_information() -> None:
    text = "\n".join(
        [
            "-----BEGIN PRIVATE KEY-----",
            "phone: " + "138" + "0013" + "8000",
            "email: person" + "@example.com",
            "id: " + "110105" + "19491231" + "002X",
        ]
    )
    rules = {finding.rule for finding in scan_text("fixture.txt", text)}

    assert rules == {"private_key", "china_phone", "email", "china_id"}


def test_placeholder_values_are_allowed() -> None:
    text = "\n".join(
        [
            "LLM_API_KEY=your_openai_compatible_api_key",
            "TOKEN=example_token_value",
            "email: omitted",
        ]
    )

    assert scan_text(".env.example", text) == []


def test_detects_lowercase_and_json_credentials() -> None:
    text = "\n".join(
        [
            'llm_api_key = "' + "A" * 24 + '"',
            '"access_token": "' + "B" * 24 + '",',
        ]
    )

    findings = scan_text("config.json", text)

    assert [finding.rule for finding in findings] == [
        "generic_credential",
        "generic_credential",
    ]

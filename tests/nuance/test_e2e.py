#!/usr/bin/env python3
"""
Optimized Frontend E2E Tests for Nuance DApp
Uses default alice wallet and focuses on front-end testing only
"""

import re
import pytest
import json
import glob
import requests
from pathlib import Path
from playwright.sync_api import Page, ConsoleMessage
from tests.utils import poll_until_condition

# Default alice wallet details from walletStore.js and chainnet.py
ALICE_ADDRESS = "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej"
ALICE_MNEMONIC = "public feature teach face federal matrix throw legend bridge brass diary beach typical doll evoke weapon among crane regret trust enact swarm brother outside"


def assert_no_unexpected_console_errors(console_messages):
    """Assert that there are no unexpected console errors, filtering out expected 404s during tx polling."""
    error_messages = [m for m in console_messages if m.type == "error"]
    
    # Filter out expected 404 errors during transaction polling
    unexpected_errors = []
    for msg in error_messages:
        # These 404 errors are expected during transaction polling before blocks are processed
        if "Failed to load resource: the server responded with a status of 404 (Not Found)" in msg.text:
            continue  # Skip expected 404s
        unexpected_errors.append(msg)
    
    assert not unexpected_errors, f"Unexpected console errors: {unexpected_errors}"


def assert_page_loads_successfully(page: Page, expected_url: str, expected_status: int = 200) -> list[ConsoleMessage]:
    """Assert that a page loads successfully with the expected status code."""
    console_messages = []
    def handle_console(msg: ConsoleMessage):
        print(f"Browser console: {msg.type} - {msg.text}")
        console_messages.append(msg)

    page.on('console', handle_console)
    
    response = page.goto(expected_url)
    page.wait_for_load_state("domcontentloaded")

    assert response is not None, f"Failed to get response from {expected_url}"
    actual_status = response.status
    assert actual_status == expected_status, (
        f"Expected status {expected_status}, got {actual_status}\n"
        f"URL: {page.url}\n"
        f"Page text content:\n{page.locator('body').inner_text()}\n"
        f"Full HTML content:\n{page.content()}"
    )

    # poll until 'walletStore init' is in the console messages
    def check_wallet_store_init():
        return any(m.text == "walletStore init" for m in console_messages)
    
    poll_until_condition(check_wallet_store_init, timeout=10, poll_interval=0.2)
    
    return console_messages


@pytest.fixture(scope="session")
def nuance_deployed(chainnet, api_address, faucet):
    """Deploy nuance script using alice account and upload all templates."""
    dysond = chainnet[0]
    
    # Get chain info
    status_result = dysond("status")
    chain_id = status_result["node_info"]["network"]
    api_port = api_address["port"]
    
    print(f"Using chain-id: {chain_id}, API port: {api_port}")
    print(f"Alice address: {ALICE_ADDRESS}")
    
    # Fund alice account using faucet
    faucet(ALICE_ADDRESS, amount=5000000)  # 5 DYS
    print(f"Funded alice with 5 DYS")
    
    # Deploy nuance script using alice
    script_path = Path(__file__).parent.parent.parent / "nuance/script.py"
    deploy_result = dysond(
        "tx", "script", "update",
        "--code-path", str(script_path),
        "--from", "alice",
        "--chain-id", chain_id,
        "--gas", "auto", "--gas-adjustment", "1.3"
    )
    assert deploy_result["code"] == 0, f"Script deployment failed: {deploy_result}"
    print(f"Deployed nuance script to alice address: {ALICE_ADDRESS}")
    
    # Upload all templates and static files
    storage_path = Path(__file__).parent.parent.parent / "nuance/storage"
    storage_files = []
    for f in glob.glob(str(storage_path / "**/*.*"), recursive=True):
        storage_key = f"{Path(f).relative_to(storage_path)}"
        storage_files.append((f, storage_key))

    for local_path, storage_key in storage_files:
        upload_result = dysond(
            "tx", "storage", "set",
            "--index", storage_key,
            "--data-path", str(local_path),
            "--from", "alice",
            "--chain-id", chain_id,
            "--gas", "auto", "--gas-adjustment", "1.3"
        )
        assert upload_result["code"] == 0, f"Template upload failed for {storage_key}: {upload_result}"
    
    print(f"Uploaded {len(storage_files)} files to storage")
    
    # Wait for script to be accessible via HTTP
    script_url = f"http://localhost:{api_port}"
    def check_script_accessible():
        response = requests.get(script_url, timeout=5, headers={"Host": f"{ALICE_ADDRESS}.localhost"}, allow_redirects=True)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        assert "<title>" in response.text
        return True

    poll_until_condition(
        check_script_accessible,
        timeout=30,
        poll_interval=0.5,
        error_message=f"Script not accessible at {script_url}"
    )
    
    return {
        "address": ALICE_ADDRESS,
        "script_url": script_url,
        "api_port": api_port
    }


@pytest.fixture(scope="function") 
def demo_url(page: Page, nuance_deployed):
    """Return the demo URL."""
    api_port = nuance_deployed["api_port"]
    url = f"http://{ALICE_ADDRESS}.localhost:{api_port}"
    print(f"Demo URL: {url}")
    console_messages = assert_page_loads_successfully(page, url)
    # poll for "DOMContentLoaded" in console messages
    def check_dom_content_loaded():
        return any(m.text == "DOMContentLoaded" for m in console_messages)
    poll_until_condition(check_dom_content_loaded, timeout=10, poll_interval=0.2)
    return url


@pytest.fixture(scope="function")
def make_post(page: Page, demo_url):
    """Fixture that returns a function to create posts with given text."""
    def _make_post(text: str) -> int:
        """Create a post with the given text and return the post ID."""
        page.set_default_timeout(5000)
        
        console_messages = assert_page_loads_successfully(page, f"{demo_url}/publish")
        print(f"Console messages: {console_messages}")
        
        assert_no_unexpected_console_errors(console_messages)
        assert page.url.endswith("/publish")
        assert page.locator("title").inner_text() == "New Post"

        # type text into post-content
        page.locator("#post-content").fill(text)

        # verify article-preview has text
        page.wait_for_selector(f"#article-preview:has-text('{text}')")
        assert page.locator("#article-preview").inner_text() == text

        # click publish
        page.locator("#postButton").click()

        # wait for confirmBtn to be visible
        page.wait_for_selector("#confirmBtn")

        # click confirmBtn
        page.locator("#confirmBtn").click()

        def check_post_id():
            page.wait_for_selector("#content")
            post_id = page.evaluate("location.href.split('/').pop()")
            return re.match(r"^\d+$", post_id) and int(post_id)

        post_id = poll_until_condition(check_post_id, timeout=10, poll_interval=0.5)
        assert post_id is not None, "Failed to get valid post ID"

        return post_id
    
    return _make_post


@pytest.fixture(scope="function")
def edit_profile(page: Page, demo_url):
    """Fixture that returns a function to edit user profiles with given text."""
    def _edit_profile(text: str) -> str:
        """Edit profile with the given text and return the author address."""
        page.set_default_timeout(5000)
        console_messages = assert_page_loads_successfully(page, demo_url)
        print(f"Console messages: {console_messages}")
        assert_no_unexpected_console_errors(console_messages)

        def wait_for_author_link():
            # Click the first .author link is visible
            link = page.wait_for_selector("a.author", state="visible")
            assert link is not None, "Failed to find author link"
            assert link.is_visible(), "Author link is not visible"
            assert link.is_enabled(), "Author link is not enabled"
            href = link.get_attribute("href")
            print(f"Author link href: {href}")
            assert href, "Author link has no href"
            
            return link

        author_link = poll_until_condition(wait_for_author_link, timeout=10, poll_interval=0.5)
        assert author_link is not None, "Failed to find author link"
        author_link.click()

        
        # Wait for URL to match /authors/<bech32 address> and extract address
        def extract_author_address():
            current_url = page.evaluate("location.href")
            match = re.search(r'/authors/(dys[a-z0-9]+)', current_url)
            assert_no_unexpected_console_errors(console_messages)

            return match.group(1) if match else None
        
        author_address = poll_until_condition(extract_author_address, timeout=10, poll_interval=0.5)
        assert author_address is not None, f"Failed to extract author address from URL"
        
        # Wait for "Edit Profile" link and click it
        page.locator("text=Edit Profile").click()
        assert_no_unexpected_console_errors(console_messages)

        # Wait for #profile-content and input the text
        page.locator("#profile-content").fill(text)
        assert_no_unexpected_console_errors(console_messages)

        # Wait and click #saveButton
        page.locator("#saveButton").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Wait for and click #confirmBtn
        page.locator("#confirmBtn").click()
        assert_no_unexpected_console_errors(console_messages)
        
        
        # Poll until URL is /authors/<bech32 address> again
        def check_back_to_profile():
            current_url = page.evaluate("location.href")
            return current_url.endswith(f"/authors/{author_address}")
        
        poll_until_condition(check_back_to_profile, timeout=10, poll_interval=0.5, 
                           error_message=f"Failed to return to profile page /authors/{author_address}")
        
        return author_address
    
    return _edit_profile


@pytest.fixture(scope="function")
def page_link(page: Page, demo_url):
    """Fixture that returns a function to create custom page links."""
    def _page_link(path: str, title: str, post_id: int, author_address: str = ALICE_ADDRESS) -> None:
        """Create a custom page link with the given path, title, and post ID."""
        page.set_default_timeout(5000)
        
        # Navigate to edit author page
        edit_url = f"{demo_url}/edit-author/{author_address}"
        console_messages = assert_page_loads_successfully(page, edit_url)
        print(f"Console messages: {console_messages}")
        
        assert_no_unexpected_console_errors(console_messages)
        assert page.url.endswith(f"/edit-author/{author_address}")
        
        # Fill in the custom page form using placeholder-based selectors
        page.locator("input[placeholder*='Path']").fill(path)
        page.locator("input[placeholder*='Page Title']").fill(title)
        page.locator("input[placeholder*='Post ID']").fill(str(post_id))
        
        # Click Add Page button (now uses text content instead of ID)
        page.locator("button:has-text('Add Page')").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Wait for and click confirmation button
        page.wait_for_selector("#confirmBtn")
        page.locator("#confirmBtn").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Wait for success message to appear (Alpine.js shows success message)
        def check_success_message():
            return page.locator(".success-message:has-text('Custom page added successfully')").is_visible()
        
        poll_until_condition(check_success_message, timeout=10, poll_interval=0.5,
                           error_message="Failed to find success message after adding custom page")
        
        # Wait for the custom page to appear in the custom pages list
        def check_page_in_list():
            # Look for the page in the Alpine.js rendered list
            page_item = page.locator(f".custom-page-item:has-text('{title}'):has-text('/{path}'):has-text('Post ID: {post_id}')")
            return page_item.is_visible()
        
        poll_until_condition(check_page_in_list, timeout=10, poll_interval=0.5,
                           error_message=f"Failed to find custom page '{title}' (/{path}) with Post ID {post_id} in the list")
        
        print(f"Successfully created custom page: {title} (/{path}) → Post #{post_id}")
    
    return _page_link


@pytest.mark.frontend 
def test_homepage_loads(page: Page, demo_url):
    """Test that the homepage loads and redirects to /recent."""
    page.set_default_timeout(5000)
    
    console_messages = assert_page_loads_successfully(page, demo_url)
    print(f"Console messages: {console_messages}")
    
    assert_no_unexpected_console_errors(console_messages)
    # Root redirects to /recent
    assert page.url.endswith("/recent")
    assert page.locator("title").inner_text() == "Post List"


@pytest.mark.frontend
def test_posts(make_post):
    """Test that posts can be created successfully."""
    post_1 = make_post("Hello, world! 1")
    
    post_2 = make_post("Hello, world! 2")
    assert post_2 > post_1, f"Post 2 ID is not greater than Post 1 ID: {post_2} > {post_1}"

@pytest.mark.frontend
def test_edit_profile(edit_profile):
    """Test that profiles can be edited successfully."""
    author_address = edit_profile("This is a test profile")
    assert author_address == ALICE_ADDRESS, f"Author address is not Alice's address: {author_address} != {ALICE_ADDRESS}"


@pytest.mark.frontend
def test_custom_page_link(make_post, page_link, demo_url, page):
    """Test that custom page links can be created successfully."""
    console_messages = assert_page_loads_successfully(page, demo_url)

    # First create a post to link to
    post_1 = make_post("This is a test post for custom page linking")
    
    # Then create a custom page link
    page_link("about", "About Me", post_1)

    post_2 = make_post("This is a new post for custom page linking")
    
    # Then create a custom page link
    page_link("new", "New", post_2)


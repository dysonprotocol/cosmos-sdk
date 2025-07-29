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
import string
import random
from pathlib import Path
from playwright.sync_api import Page, ConsoleMessage
from tests.utils import poll_until_condition

# Default alice wallet details from walletStore.js and chainnet.py
ALICE_ADDRESS = "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej"
ALICE_MNEMONIC = "public feature teach face federal matrix throw legend bridge brass diary beach typical doll evoke weapon among crane regret trust enact swarm brother outside"


def assert_no_unexpected_console_errors(console_messages):
    """Assert that there are no unexpected console errors, filtering out expected errors."""
    error_messages = [m for m in console_messages if m.type == "error"]
    
    # Filter out expected errors using list comprehension
    expected_error_texts = [
        "Failed to load resource: the server responded with a status of 404 (Not Found)",  # Tx polling 404s
        "[WalletStore] Error fetching names for address",  # Expected when no names are registered
        "TypeError: Failed to fetch"  # Expected fetch errors during initialization
    ]
    
    # Keep only unexpected errors (those not matching any expected pattern)
    unexpected_errors = [
        msg for msg in error_messages 
        if not any(expected_text in msg.text for expected_text in expected_error_texts)
    ]
    
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
    
    # Set BASE_DOMAIN in settings storage
    base_domain = f"http://{ALICE_ADDRESS}.localhost:{api_port}"
    settings_data = json.dumps({"BASE_DOMAIN": base_domain})
    settings_result = dysond(
        "tx", "storage", "set",
        "--index", "settings",
        "--data", settings_data,
        "--from", "alice",
        "--chain-id", chain_id,
        "--gas", "auto", "--gas-adjustment", "1.3"
    )
    assert settings_result["code"] == 0, f"Settings storage failed: {settings_result}"
    print(f"Set BASE_DOMAIN to: {base_domain}")
    
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
    post_counter = [0]  # Use list to allow mutation in nested function
    
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

        # verify article-preview contains the text
        page.wait_for_selector(f"#article-preview:has-text('{text}')")
        assert text in page.locator("#article-preview").inner_text()

        # click publish
        page.locator("#postButton").click()

        # wait for confirmBtn to be visible
        page.wait_for_selector("#confirmBtn")

        # click confirmBtn
        page.locator("#confirmBtn").click()

        # Most reliable for HTMX SPAs: wait for URL to change using Playwright's built-in method
        # This handles all async timing automatically
        page.wait_for_url(re.compile(r'/\d+'), timeout=10000)
        
        # Now extract the post ID from the URL
        current_url = page.url
        print(f"DEBUG: Successfully navigated to: {current_url}")
        
        # Extract post ID from URL
        match = re.search(r'/(\d+)(?:\?|$|#|/)', current_url)
        assert match, f"Could not extract post ID from URL: {current_url}"
        
        post_id = int(match.group(1))
        print(f"DEBUG: SUCCESS - Post created with ID: {post_id}")
        
        return post_id
    
    return _make_post


@pytest.fixture(scope="function")
def edit_profile(page: Page, demo_url, make_post):
    """Fixture that returns a function to edit user profiles with given text."""
    def _edit_profile(text: str) -> str:
        """Edit profile with the given text and return the author address."""
        page.set_default_timeout(5000)
        console_messages = assert_page_loads_successfully(page, demo_url)
        print(f"Console messages: {console_messages}")
        assert_no_unexpected_console_errors(console_messages)

        # Check if there are any author links on the page, if not create a post first
        author_links = page.locator("a.author").count()
        
        # If no author links exist, create a post first
        
        post_id = make_post("Test post for profile editing")
        print(f"Created post {post_id} to ensure author links exist")
        
        # Now navigate back to the demo_url to see the author link
        console_messages = assert_page_loads_successfully(page, demo_url)
        assert_no_unexpected_console_errors(console_messages)

        def wait_for_author_link_and_extract_address():
            # Find the author link and extract address from href before clicking
            link = page.wait_for_selector("a.author", state="visible")
            assert link is not None, "Failed to find author link"
            assert link.is_visible(), "Author link is not visible"
            assert link.is_enabled(), "Author link is not enabled"
            href = link.get_attribute("href")
            print(f"Author link href: {href}")
            assert href, "Author link has no href"
            
            # Extract author address from href before clicking (avoids HTMX navigation timing issues)
            match = re.search(r'/authors/(dys[a-z0-9]+)', href)
            author_address = match.group(1) if match else None
            assert author_address, f"Could not extract author address from href: {href}"
            
            return link, author_address

        author_link, author_address = poll_until_condition(wait_for_author_link_and_extract_address, timeout=10, poll_interval=0.5)
        assert author_link is not None, "Failed to find author link"
        assert author_address is not None, f"Failed to extract author address"
        
        # Now click the link and wait for navigation
        author_link.click()
        
        # Wait for author page content to appear
        page.wait_for_selector("text=Edit Profile", state="visible")
        page.wait_for_selector("h1.author", state="visible")
        
        # Wait for "Edit Profile" link and click it
        page.locator("text=Edit Profile").click()
        assert_no_unexpected_console_errors(console_messages)

        # Wait for profile content textarea and input the text
        page.locator('textarea[name="content"]').fill(text)
        assert_no_unexpected_console_errors(console_messages)

        # Wait and click Save Profile button
        page.locator("button:has-text('Save Profile')").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Wait for and click #confirmBtn
        page.locator("#confirmBtn").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Most reliable for HTMX SPAs: wait for URL to change back to author profile page
        # This confirms navigation away from edit page (/edit-author/xxx) back to profile page (/authors/xxx)
        author_profile_url_pattern = re.compile(f'/authors/{re.escape(author_address)}')
        page.wait_for_url(author_profile_url_pattern, timeout=10000)
        
        print(f"DEBUG: Successfully navigated back to author profile: {page.url}")
        
        # Now verify the profile text appears on the page (not in a form field)
        # Wait for the text to appear in rendered content
        def check_profile_content_saved():
            # Check specifically for the rendered profile content (paragraph elements)
            # This ensures we're seeing the saved content, not form fields
            paragraph_with_text = page.locator("p").filter(has_text=text)
            paragraph_visible = paragraph_with_text.count() > 0 and paragraph_with_text.first.is_visible()
            
            # Also check markdown rendered areas
            markdown_with_text = page.locator(".markdown").filter(has_text=text)
            markdown_visible = markdown_with_text.count() > 0 and markdown_with_text.first.is_visible()
            
            found = paragraph_visible or markdown_visible
            found and print(f"✓ Profile text '{text}' found in rendered content")
            
            return found
        
        poll_until_condition(check_profile_content_saved, timeout=10, poll_interval=0.3, 
                           error_message=f"Failed to find saved profile text '{text}' on author profile page")
        
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
        page.locator("input[placeholder*='about']").fill(path)
        page.locator("input[placeholder*='Optional page title']").fill(title)
        page.locator("input[placeholder*='e.g., 123']").fill(str(post_id))
        
        # Click Add button
        page.locator("button:has-text('Add')").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Wait for and click confirmation button
        page.wait_for_selector("#confirmBtn")
        page.locator("#confirmBtn").click()
        assert_no_unexpected_console_errors(console_messages)
        
        # Wait for success message to appear (Alpine.js shows success message)
        def check_success_message():
            return page.locator(".alert:has-text('successfully')").is_visible()
        
        poll_until_condition(check_success_message, timeout=10, poll_interval=0.5,
                           error_message="Failed to find success message after adding custom page")
        
        # Wait for the custom page to appear in the custom pages list
        def check_page_in_list():
            # Look for the page in the table - check for the path and post ID
            path_cell = page.locator(f"td:has-text('/{path}')")
            post_cell = page.locator(f"td:has-text('Post #{post_id}')")
            return path_cell.is_visible() and post_cell.is_visible()
        
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


def generate_random_path(length=5):
    """Generate a random path of specified length using lowercase letters."""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


@pytest.mark.frontend
def test_custom_page_link(make_post, page_link, demo_url, page):
    """Test that custom page links can be created successfully."""
    console_messages = assert_page_loads_successfully(page, demo_url)

    # First create a post to link to
    post_1 = make_post("This is a test post for custom page linking")
    
    # Create a custom page link with random path to ensure uniqueness
    random_path_1 = generate_random_path()
    page_link(random_path_1, "About Me", post_1)

    post_2 = make_post("This is a new post for custom page linking")
    
    # Create another custom page link with different random path
    random_path_2 = generate_random_path()
    page_link(random_path_2, "New Page", post_2)


@pytest.mark.frontend
def test_custom_page_link_replacement(make_post, demo_url, page):
    """Test that custom page links can be replaced/updated successfully."""
    page.set_default_timeout(5000)
    console_messages = assert_page_loads_successfully(page, demo_url)

    # Create two posts
    post_1 = make_post("First post for path replacement test")
    post_2 = make_post("Second post for path replacement test")
    
    # Use a specific path for testing replacement
    test_path = "testpath"
    
    # Navigate to edit author page
    edit_url = f"{demo_url}/edit-author/{ALICE_ADDRESS}"
    console_messages = assert_page_loads_successfully(page, edit_url)
    
    # First, create a custom page link
    page.locator("input[placeholder*='about']").fill(test_path)
    page.locator("input[placeholder*='Optional page title']").fill("Original Title")
    page.locator("input[placeholder*='e.g., 123']").fill(str(post_1))
    page.locator("button:has-text('Add')").click()
    
    # Wait for and click confirmation button
    page.wait_for_selector("#confirmBtn")
    page.locator("#confirmBtn").click()
    
    # Wait for success message
    page.wait_for_selector(".alert:has-text('successfully')", state="visible")
    
    # Wait for the page to appear in the list
    page.wait_for_selector(f"td:has-text('/{test_path}')", state="visible")
    
    # Now replace it with a new post - this should work without error
    page.locator("input[placeholder*='about']").fill(test_path)
    page.locator("input[placeholder*='Optional page title']").fill("Updated Title")
    page.locator("input[placeholder*='e.g., 123']").fill(str(post_2))
    page.locator("button:has-text('Add')").click()
    
    # Wait for and click confirmation button
    page.wait_for_selector("#confirmBtn")
    page.locator("#confirmBtn").click()
    
    # Wait for success message - should say "updated" since we're replacing
    page.wait_for_selector(".alert:has-text('Custom page updated successfully')", state="visible")
    
    # Verify the page list shows the updated post ID
    def check_page_updated():
        # Look for the page in the table - should show the new post ID
        post_cell = page.locator(f"td:has-text('Post #{post_2}')")
        return post_cell.is_visible()
    
    poll_until_condition(check_page_updated, timeout=5, poll_interval=0.2,
                        error_message=f"Failed to find updated page with Post ID {post_2} in the list")
    
    # The update should have worked - the important part is that replacement is allowed
    # without throwing an error, which we've already verified above
    print(f"Successfully replaced custom page link: /{test_path} now points to post {post_2}")


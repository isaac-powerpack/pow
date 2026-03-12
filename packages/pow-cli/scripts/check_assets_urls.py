#!/usr/bin/env python3
"""Check asset URLs from TOML registries to verify they are downloadable."""

import asyncio
import sys
from pathlib import Path
from typing import NamedTuple

import aiohttp
import tomlkit

# Adjust path based on script location
SCRIPT_DIR = Path(__file__).parent
POW_CLI_DIR = SCRIPT_DIR.parent
REGISTRY_DIR = POW_CLI_DIR / "pow_cli" / "data" / "asset-registry"


class AssetUrl(NamedTuple):
    name: str
    url: str
    source_file: str
    category: str


def load_isaac_sim_assets() -> list[AssetUrl]:
    """Load Isaac Sim assets from TOML file."""
    toml_path = REGISTRY_DIR / "isaacsim_assets_5_1_0.toml"
    with open(toml_path) as f:
        data = tomlkit.parse(f.read())

    assets = []
    for pack in data.get("isaac_sim_assets", {}).get("packs", []):
        assets.append(
            AssetUrl(
                name=pack.get("name", "Unknown"),
                url=pack.get("url", ""),
                source_file="isaacsim_assets_5_1_0.toml",
                category="isaac_sim",
            )
        )
    return assets


def load_omniverse_assets() -> list[AssetUrl]:
    """Load Omniverse assets from TOML file."""
    toml_path = REGISTRY_DIR / "omniverse_assets.toml"
    with open(toml_path) as f:
        data = tomlkit.parse(f.read())

    assets = []
    omniverse_data = data.get("omniverse", {})

    # Extract all array items from different categories
    for category in ["3d_assets", "sim_ready", "materials", "environments", "workflows"]:
        for asset in omniverse_data.get(category, []):
            assets.append(
                AssetUrl(
                    name=asset.get("name", "Unknown"),
                    url=asset.get("url", ""),
                    source_file="omniverse_assets.toml",
                    category=category,
                )
            )
    return assets


async def test_url(
    session: aiohttp.ClientSession, asset: AssetUrl, timeout: int = 30
) -> tuple[AssetUrl, bool, str, int | None]:
    """Test if a URL is accessible using HEAD request."""
    try:
        async with session.head(
            asset.url,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            status = response.status
            success = status in (200, 206)  # 200 OK, 206 Partial Content
            message = f"HTTP {status}"
            content_length = response.headers.get("Content-Length")
            return asset, success, message, int(content_length) if content_length else None
    except asyncio.TimeoutError:
        return asset, False, "Timeout", None
    except aiohttp.ClientError as e:
        return asset, False, f"Error: {type(e).__name__}", None
    except Exception as e:
        return asset, False, f"Exception: {e}", None


async def test_all_urls(concurrency: int = 10) -> dict:
    """Test all asset URLs concurrently."""
    # Collect all assets
    all_assets = []
    all_assets.extend(load_isaac_sim_assets())
    all_assets.extend(load_omniverse_assets())

    print(f"Found {len(all_assets)} URLs to test\n")

    results = {"success": [], "failed": []}

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(concurrency)

    async def limited_test(session: aiohttp.ClientSession, asset: AssetUrl):
        async with semaphore:
            return await test_url(session, asset)

    async with aiohttp.ClientSession() as session:
        tasks = [limited_test(session, asset) for asset in all_assets]
        results_list = await asyncio.gather(*tasks)

    # Categorize results
    for asset, success, message, size in results_list:
        if success:
            results["success"].append((asset, message, size))
        else:
            results["failed"].append((asset, message, size))

    return results


def print_results(results: dict) -> bool:
    """Print test results in a formatted way."""
    success_count = len(results["success"])
    failed_count = len(results["failed"])
    total = success_count + failed_count

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total URLs tested: {total}")
    print(f"✓ Successful: {success_count}")
    print(f"✗ Failed: {failed_count}")

    def format_size(size_bytes: int | None) -> str:
        if size_bytes is None:
            return ""
        size_gb = size_bytes / (1024**3)
        return f" ({size_gb:.2f} GB)"

    def print_group(group_results, title):
        if not group_results:
            return
        
        print("\n" + "-" * 40)
        print(f" GROUP: {title}")
        print("-" * 40)
        
        for asset, message, size in group_results:
            size_str = format_size(size)
            symbol = "✓" if message.startswith("HTTP 2") else "✗"
            if symbol == "✓":
                print(f"{symbol} {asset.name}{size_str}")
            else:
                print(f"{symbol} {asset.name}")
                print(f"  URL: {asset.url}")
                print(f"  Error: {message}")

    if results["failed"] or results["success"]:
        # Split results into Isaac Sim and Omniverse
        isaac_success = [r for r in results["success"] if "isaacsim" in r[0].source_file]
        isaac_failed = [r for r in results["failed"] if "isaacsim" in r[0].source_file]
        
        omni_success = [r for r in results["success"] if "omniverse" in r[0].source_file]
        omni_failed = [r for r in results["failed"] if "omniverse" in r[0].source_file]

        print("\n" + "=" * 70)
        print("ISAAC SIM ASSETS")
        print("=" * 70)
        print_group(isaac_success, "Successful")
        print_group(isaac_failed, "Failed")

        print("\n" + "=" * 70)
        print("OMNIVERSE ASSETS")
        print("=" * 70)
        print_group(omni_success, "Successful")
        print_group(omni_failed, "Failed")

    return success_count == total


def main():
    """Main entry point."""
    print("Checking asset registry URLs...")
    print(f"Registry directory: {REGISTRY_DIR}\n")

    results = asyncio.run(test_all_urls(concurrency=10))
    all_passed = print_results(results)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

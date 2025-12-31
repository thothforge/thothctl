#!/usr/bin/env python3
"""Standalone utility to check and fix HTML report styling consistency."""

import argparse
import glob
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import our utilities
sys.path.insert(0, str(Path(__file__).parent))

from report_html_utils import HTMLReportUtils


def find_html_reports(directory: str) -> list:
    """Find all HTML reports in a directory and its subdirectories."""
    html_files = []
    
    # Look for HTML files recursively
    for pattern in ["*.html", "**/*.html"]:
        html_files.extend(glob.glob(os.path.join(directory, pattern), recursive=True))
    
    return html_files


def check_reports(directory: str, fix: bool = False) -> dict:
    """Check all HTML reports in a directory for consistency."""
    html_files = find_html_reports(directory)
    
    if not html_files:
        print(f"No HTML files found in {directory}")
        return {"total": 0, "consistent": 0, "fixed": 0, "failed": 0}
    
    print(f"Found {len(html_files)} HTML files to check")
    
    results = {
        "total": len(html_files),
        "consistent": 0,
        "fixed": 0,
        "failed": 0,
        "reports": []
    }
    
    for html_file in html_files:
        print(f"\nChecking: {html_file}")
        
        validation = HTMLReportUtils.validate_report_consistency(html_file)
        
        report_info = {
            "file": html_file,
            "validation": validation,
            "fixed": False
        }
        
        if not validation["issues"]:
            print("  ✅ Report is consistent")
            results["consistent"] += 1
        else:
            print(f"  ⚠️  Issues found: {', '.join(validation['issues'])}")
            
            if fix:
                print("  🔧 Attempting to fix...")
                if HTMLReportUtils.fix_report_consistency(html_file):
                    print("  ✅ Fixed successfully")
                    results["fixed"] += 1
                    report_info["fixed"] = True
                else:
                    print("  ❌ Failed to fix")
                    results["failed"] += 1
            else:
                print("  💡 Use --fix to attempt automatic fixes")
        
        results["reports"].append(report_info)
    
    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check and fix HTML report styling consistency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check reports in current directory
  python fix_report_styling.py .
  
  # Check and fix reports in a specific directory
  python fix_report_styling.py /path/to/reports --fix
  
  # Check reports in ThothCTL scan output
  python fix_report_styling.py ./Reports --fix
        """
    )
    
    parser.add_argument(
        "directory",
        help="Directory to scan for HTML reports"
    )
    
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix consistency issues automatically"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed validation information"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)
    
    print(f"🔍 Scanning for HTML reports in: {args.directory}")
    
    results = check_reports(args.directory, fix=args.fix)
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total reports checked: {results['total']}")
    print(f"Already consistent: {results['consistent']}")
    
    if args.fix:
        print(f"Successfully fixed: {results['fixed']}")
        print(f"Failed to fix: {results['failed']}")
    else:
        issues_found = results['total'] - results['consistent']
        if issues_found > 0:
            print(f"Reports with issues: {issues_found}")
            print("💡 Run with --fix to attempt automatic fixes")
    
    if args.verbose:
        print("\nDETAILED RESULTS:")
        for report in results["reports"]:
            print(f"\n📄 {report['file']}")
            validation = report['validation']
            
            if validation['issues']:
                print(f"  Issues: {', '.join(validation['issues'])}")
                if report['fixed']:
                    print("  Status: ✅ Fixed")
                elif args.fix:
                    print("  Status: ❌ Failed to fix")
                else:
                    print("  Status: ⚠️  Needs fixing")
            else:
                print("  Status: ✅ Consistent")
    
    # Exit with appropriate code
    if results['failed'] > 0:
        sys.exit(1)
    elif results['total'] - results['consistent'] - results['fixed'] > 0:
        sys.exit(2)  # Issues found but not fixed
    else:
        sys.exit(0)  # All good


if __name__ == "__main__":
    main()

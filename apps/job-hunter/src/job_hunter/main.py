#!/usr/bin/env python3
"""Main entry point for AI Job Hunter"""
import argparse
import sys
from job_hunter.config import Config
from job_hunter.orchestrator import JobApplicationOrchestrator
from job_hunter.app import run_app


def run_cli(resume_path: str, user_id: str = "default_user"):
    """Run job hunter in CLI mode"""
    try:
        # Validate configuration
        Config.validate()

        # Create orchestrator and run
        orchestrator = JobApplicationOrchestrator(user_id)
        result = orchestrator.run(resume_path)
        orchestrator.cleanup()

        if result['success']:
            print("\nJob hunting session completed successfully!")
            return 0
        else:
            print(f"\nJob hunting failed: {result.get('message', 'Unknown error')}")
            return 1

    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1


def run_web():
    """Run job hunter in web mode"""
    try:
        print("Starting AI Job Hunter Web App...")
        print(f"Access the dashboard at: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
        run_app()
    except Exception as e:
        print(f"\nError starting web app: {str(e)}")
        return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AI Job Hunter - Automated job application system using MobileRun AI"
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # CLI mode
    cli_parser = subparsers.add_parser('apply', help='Apply to jobs using resume')
    cli_parser.add_argument('resume', help='Path to resume PDF file')
    cli_parser.add_argument('--user-id', default='default_user', help='User ID (default: default_user)')

    # Web mode
    subparsers.add_parser('web', help='Start web application')

    args = parser.parse_args()

    if args.command == 'apply':
        sys.exit(run_cli(args.resume, args.user_id))
    elif args.command == 'web':
        sys.exit(run_web())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

cd /Users/soumyayotimohanta/Developer/hackathon/monorepo/

# Start all services concurrently with pm2
pm2 delete gateway job-hunter web 2>/dev/null || true

pm2 start "uv run uvicorn ironclaw.main:app --reload --host 0.0.0.0 --port 8000" \
	--name gateway \
	--cwd /Users/soumyayotimohanta/Developer/hackathon/monorepo/apps/gateway

pm2 start "uv run python -m job_hunter.main web" \
	--name job-hunter \
	--cwd /Users/soumyayotimohanta/Developer/hackathon/monorepo/apps/job-hunter

pm2 start "npm run dev" \
	--name web \
	--cwd /Users/soumyayotimohanta/Developer/hackathon/monorepo/apps/web

pm2 save
pm2 status

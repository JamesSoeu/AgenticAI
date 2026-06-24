# Transportation Agents Monorepo

This is the merged end-to-end repository for the Gemini Enterprise
transportation multi-agent system.

```text
data-agent/    Data A2A agent for BigQuery, Cloud Storage, and PDFs
map-agent/     A2A + A2UI Google Maps bridge inventory agent
router-agent/  Orchestrator/router A2A agent registered with Gemini Enterprise
docs/          Architecture, team workflow, and deployment guide
```

Start with:

```text
docs/TEAM_AND_REPO_GUIDE.md
```

Production recommendation:

```text
One Git repo
One Google Cloud project
Three Cloud Run services
One Gemini Enterprise registration: the router agent card
```

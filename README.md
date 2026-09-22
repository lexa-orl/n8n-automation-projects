# n8n Automation Projects

A collection of workflow automation projects built with n8n, REST APIs, Telegram, Supabase, Google Sheets, and LLM services.

## Projects

| Project | What it demonstrates |
| --- | --- |
| [VPN Telegram Bot](./01-vpn-telegram-bot/) | Product-like Telegram bot with user state, database records, and VPN provisioning APIs |
| [Wildberries SEO Pipeline](./02-wildberries-seo-pipeline/) | Batch data processing, validation rules, Google Sheets updates, and status-driven operations |
| [Smart GitHub Finder](./03-smart-github-finder/) | AI query generation, GitHub search, deduplication, scoring, ranking, and chat output |
| [AI Content Factory](./04-ai-content-factory/) | Scheduled content generation, validation, approval flow, and Telegram publishing |

## Technical focus

- Event-driven workflows with Telegram, webhook, chat, and schedule triggers
- REST API integrations with authentication and multi-step operations
- Supabase and Google Sheets as operational data stores
- LLM pipelines using OpenRouter and n8n AI nodes
- JavaScript transformations, routing, batching, and state-based logic
- Workflow decomposition with sub-workflows

## Project notes

Each project documents the business problem, workflow architecture, integrations, limitations, and possible production improvements. Credentials, tokens, private IDs, and customer data are intentionally excluded from this repository.

## Running the examples

1. Import the sanitized JSON workflow into n8n.
2. Create your own credentials for the referenced services.
3. Replace placeholder IDs and URLs with test values.
4. Run with mock or development data first.

These public exports use placeholders and should be reviewed before production use.

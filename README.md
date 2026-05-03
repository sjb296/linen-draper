# Linen Draper

> Cockney rhyming slang for "newspaper"

Manual intervention tracker for Arch/Artix. Email reports and web dashboard.

## Why?

Recently, I decided to totally ditch Windows on my personal hardware. I use Artix on my PC now and I'm loving it! One problem people often have with Arch, though it's more of a meme nowadays, is package upgrades borking their system. This project exists to guard against this, and also to test out the Reflex framework, Zed and OpenCode with Chinese LLMs.

## The stack

- Language of choice: Python
- Web framework: reflex.dev
- Environment management: `uv`
- Database: sqlite
- Reverse proxy: Caddy
- Anti-scraper: Anubis
- VM host: Ubuntu

## The outcome

My £1.20/month VM with 1GB of memory, unsurprisingly, couldn't run it! Verdict: Works on my machine!™

# Magicpin Merchant AI Assistant

## Overview

This project is a FastAPI-based Merchant AI Assistant built for the Magicpin AI Challenge.

The bot receives merchant, category, customer, and trigger contexts through HTTP endpoints and generates context-aware responses for merchants.

## Features

- Context storage with version handling
- Trigger-based message generation
- Category-aware responses
- Merchant-specific personalization
- Conversation memory
- Intent detection
- WhatsApp auto-reply detection
- REST API built with FastAPI
- Public deployment on Render

## API Endpoints

- GET /v1/healthz
- GET /v1/metadata
- POST /v1/context
- POST /v1/tick
- POST /v1/reply

## Technology

- Python
- FastAPI
- Uvicorn
- GitHub
- Render

## Deployment

Public URL:

https://magicpin-bot-3q50.onrender.com

## Author

Ravinder Singh
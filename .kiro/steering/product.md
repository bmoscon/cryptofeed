# Product Overview

## Summary
Cryptofeed is an open-source cryptocurrency market data platform that streams
and normalises public and private exchange feeds for quantitative trading and
analytics workloads. The feed handler abstracts exchange-specific transport
details (REST, WebSocket, CCXT/CCXT-Pro) and emits standardised trade, order
book, ticker, funding, and account events to user-defined callbacks or
prebuilt backends.

## Core Features
- **Unified Feed Handler:** Single `FeedHandler` orchestrating dozens of native
  connectors plus a generic CCXT/CCXT-Pro layer for long-tail exchanges.
- **Normalised Data Models:** Consistent `Trade`, `OrderBook`, NBBO, and account
  events with sequence tracking to simplify downstream pipelines.
- **Proxy-First Connectivity:** Centralised proxy resolver with per-exchange
  HTTP/WebSocket overrides and pool-aware selection, enabling restricted or
  region-specific deployments.
- **Asynchronous Architecture:** Event-driven asyncio transports that favour
  WebSocket streams, fall back to REST snapshots, and scale across exchanges.
- **Extensible Backends:** Built-in adapters for Redis, Arctic, ZeroMQ, sockets,
  and custom callbacks, plus examples for live ingestion and storage.
- **Spec-Driven Roadmap:** Active initiatives such as the CCXT generic
  refactor, Backpack integration, and a streaming lakehouse architecture keep
  the platform aligned with FR-first delivery principles.

## Target Use Cases
- Quantitative researchers needing clean, historical market data for
  backtesting or signal modelling.
- Trading infrastructure teams operating multi-exchange execution or market
  surveillance systems who require low-latency book and trade feeds.
- Data engineering groups building real-time analytics pipelines or data
  lakehouse ingestion layers for digital asset markets.
- Builders who need rapid prototyping of exchange connectivity without
  exchanging bespoke API code for each venue.

## Value Proposition
- **Reduced Integration Cost:** Abstracts heterogeneous exchange APIs behind a
  stable interface, slashing onboarding time for new venues.
- **Operational Consistency:** Proxy-aware transports, shared retry logic, and
  typed configuration improve reliability across environments.
- **Future-Proof Extensibility:** Declarative hooks for symbol/price
  normalisation, adapter registries, and spec-aligned refactors allow new
  capabilities without legacy baggage.
- **Community Ecosystem:** Extensive examples, documentation, and an adjacent
  Cryptostore project provide end-to-end ingestion and storage patterns.

## Current Roadmap Highlights (Q4 2025)
- **ccxt-generic-pro-exchange:** Consolidate CCXT transports, adapters, and
  configuration under a cohesive package with proxy-aligned behaviour.
- **backpack-exchange-integration:** Deliver Backpack support leveraging the
  generic CCXT layer and proxy-first transports.
- **cryptofeed-lakehouse-architecture:** Define lakehouse ingestion patterns
  for unified historical and real-time analytics.
- **proxy-system-complete:** Maintain the newly shipped proxy injector and
  documentation, ensuring all transports default to the shared system.


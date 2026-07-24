# AI-Powered Logistics Analytics Dashboard

## Project Specification

## Overview

Design, build, and deploy an AI-powered analytics dashboard for a logistics client.

This assignment evaluates your ability to build a full-stack application that:

- Handles structured data
- Delivers meaningful analytics
- Integrates AI responsibly
- Implements forecasting
- Ships to production
- Communicates technical decisions with clarity

## Project Summary

Build a web application with two complementary interfaces:

- A traditional analytics dashboard showing KPIs and charts
- A natural-language interface powered by AI

Together they should support querying operational data, generating charts dynamically, answering business questions, and predicting demand.

## Core Concept

The application must operate on one unified dataset and support three levels of intelligence:

| Level | Purpose |
|---|---|
| Descriptive Analytics | Dashboards and visualizations that show what has happened. |
| Diagnostic Analytics | Natural-language queries answered directly from data—explaining why. |
| Predictive & Prescriptive Analytics | Forecasting future demand and recommending action. |

## Core Requirements

### Dashboard

Create a dashboard displaying at minimum:

- Total orders
- Delivered orders
- Delayed orders
- On-time delivery rate
- Average delivery time

Support at least two charts, for example:

- Order volume over time
- Delivery performance (delayed vs. on-time)
- Carrier or destination breakdown

### Natural Language Queries

Users must be able to ask questions such as:

- “Show delayed orders by week for the last 3 months”
- “Which carrier has the highest delay rate?”
- “How many orders were delivered late last month?”

The system should interpret each question, retrieve the relevant data, and return a direct answer, a chart, or both.

### Dynamic Chart Generation

The system must automatically select an appropriate chart type, render charts dynamically, and support a defined subset of analytical queries.

### Explainability

Every answer or chart must be accompanied by:

- The filters applied, such as a time range
- The metrics and dimensions used
- A query plan or structured interpretation (recommended)
- Access to the underlying data as a table or summary

### Data Handling

Use the provided dataset or database. Treat all data as read-only and ensure correct aggregation and filtering throughout.

## AI-Orchestrated Analytical Tools

The AI layer must act as a routing and orchestration system—not as the source of truth. AI should interpret the user’s question, select the correct computation path, call the appropriate tool, and present results clearly. It must never generate answers without computation.

### A. Query Tool (Analytics)

Used for dashboard queries, aggregations, and KPI calculations. Handles questions like:

- “Show delayed orders by week”
- “Which carrier has the highest delay rate?”

### B. Forecasting Tool

Used for predicting future demand. Handles questions like:

- “Predict demand for SKU X for the next 4 months”
- “How much inventory should I plan?”

The tool must:

- Use historical data from the dataset
- Apply a basic forecasting method
- Return forecast values
- Visualize historical and forecast data
- Return an inventory recommendation
- Explain the methodology

Acceptable methods include moving average, linear regression, exponential smoothing, and simple trend models.

### Expected System Flow

```text
User Question
→ AI Interpretation
→ Tool Selection
→ Structured Input
→ Computation
→ Result
→ Explanation
→ Visualization
```

## Deployment Requirements

The application must be:

- Deployed to a publicly accessible URL
- Fully usable without local setup
- Stable for reviewers

Any hosting platform is acceptable, such as Vercel or AWS. If authentication is used, provide test credentials. Do not commit secrets to the repository.

## Technical Expectations

Any technology stack is acceptable. Common choices include:

- React, Next.js, or Vue for the frontend
- Node, Python, Java, or .NET for the backend
- PostgreSQL for the database

## Architecture Guidelines

- Avoid executing raw AI-generated SQL without validation
- Prefer structured query generation
- Clearly separate AI interpretation, data computation, and business logic

## Deliverables

Submit:

- A source code repository
- A live deployed application URL
- A `README.md`

### README Requirements

The README must cover:

- Local setup instructions and environment variables
- A system overview with key design decisions and data flow
- How questions are interpreted and tools are selected
- Assumptions and simplifications
- Limitations and unsupported queries
- Future improvements

## Evaluation Criteria

| Category | Weight |
|---|---:|
| Product & UX | 15% |
| Frontend | 15% |
| Backend & Architecture | 20% |
| Data Correctness | 20% |
| AI Orchestration | 15% |
| Forecasting | 10% |
| Deployment | 5% |

## Important Notes

Expected effort is 6–10 hours. We value clarity, correctness, and reasoning over completeness and polish. Prefer simple, correct solutions and explain your tradeoffs. Do not over-engineer. Undisclosed AI usage may be treated negatively.

## Submission

Provide:

- Repository link
- Deployed app URL
- Credentials, if authentication is required


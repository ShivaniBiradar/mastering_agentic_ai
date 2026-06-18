# AlloChef Project Submission

## One-Liner

My agent helps multi-diet families ask "what can we cook tonight?" in a Streamlit chat interface, replacing the manual workflow of checking recipes, comparing family allergies, searching substitutions, and building a grocery list across multiple tabs. It interprets the user's meal-planning request, retrieves recipes, checks allergens, finds safe substitutions, scans fridge photos, compares pantry items, and prepares a human-approved cart draft using 8 tools/systems, hands off to a human before any cart is approved or shopping action is taken, and I'll know it works when a parent can get from a natural-language question to a usable allergen-safe meal plan in under 5 minutes with grounded suggestions at least 8 times out of 10.

## Agent System Table

| Field | Fill in |
|---|---|
| Agent goal | AlloChef helps a household move from a conversational meal-planning question, such as "what can we cook tonight?", to a safe dinner plan with substitutions and grocery support. The goal is end-to-end meal decision support, not just answering a recipe question. |
| Where do people use it? | People use it in a Streamlit chat interface where they can ask a natural-language meal question, scan a fridge/grocery photo, select family members, open recipe cards, and optionally plan groceries from a chosen recipe. |
| What steps does it take, in order? | 1. The user asks a meal-planning question in chat or provides ingredients/image input. 2. The Meal Orchestrator interprets intent and routes recipe requests to the Recipe Recommender or grocery requests to the Grocery Agent. 3. The recommender invokes the LangGraph recipe pipeline. 4. The graph retrieves recipes, checks relevance, checks allergens, routes unsafe recipes to the Substitution Agent, generates a grounded response, and verifies it. 5. If the user chooses a recipe, the Grocery Agent runs deterministic pantry/safety checks, uses the shared substitution layer for unsafe missing items, and prepares a cart draft for human approval. |
| What can it actually do? | It can route user intent, scan images for ingredients, retrieve recipes, evaluate relevance, verify allergen conflicts, query Neo4j for curated substitution candidates, use Pinecone semantic fallback for substitutes, use the Substitution Agent to choose context-aware swaps, compare a selected recipe against pantry items, and prepare a grocery/cart draft. Read and recommendation actions can run autonomously; cart creation is gated by explicit human approval. |
| What does it need to remember? | It remembers family member profiles, allergens, and pantry items across sessions in SQLite. During a single run, LangGraph state tracks ingredients, restrictions, retrieved recipes, unsafe pairs, substitutions, relevance checks, hallucination checks, and the generated response. |
| What should it never do? | It should never invent unsupported recipes, ignore an active allergen restriction, recommend an unsafe substitute, or create/approve a grocery cart without human confirmation. It should also never treat a model answer as authoritative when deterministic safety checks disagree. |
| Human-in-the-loop | The human selects which family members are eating, reviews recipe suggestions, expands recipe cards, and must approve any grocery/cart draft before it is finalized. The app can read and suggest autonomously, but write/purchase-style actions require approval. |
| What happens when something breaks? | If retrieval is weak, the graph retries with a rewritten query; if generation is not grounded, it regenerates with a stricter prompt and then falls back honestly if needed. If Neo4j has no substitution or a service fails, the agent either falls back to another lookup path or stops safely instead of fabricating a result. |
| How do you know it worked? | It works when a user can ask a natural-language meal question, select family restrictions, and reach a usable dinner plan with substitutions and grocery guidance in under 5 minutes. A practical success target is that 8 out of 10 demo users would accept at least one suggested plan as usable for their household. |

## Short Project Summary

AlloChef is an agentic meal-planning system for families with allergies and mixed dietary needs. The user interacts through a Streamlit chat interface: they can ask what to cook, provide ingredients, scan a fridge photo, and move from a question to recipe cards, substitutions, and grocery planning.

Behind that chat surface, AlloChef combines a top-level Meal Orchestrator, specialist recipe and grocery agents, a substitution agent, deterministic safety tools, persistent family/pantry memory, and a Streamlit interface.

The app is designed around end-to-end task completion, not a single model response. A successful run means the user moves from "what can we cook tonight with what we have?" to "here are recipes I can cook, these are the substitutions if needed, and this is what I need to buy."

## Agentic System Design

The current architecture is a multi-agent system with a clear separation of responsibility:

| Component | Role |
|---|---|
| Meal Orchestrator | Top-level agent that decides whether the user wants recipe recommendations or grocery planning. |
| Recipe Recommender | Specialist agent that extracts available ingredients and calls the recipe search pipeline. |
| LangGraph recipe pipeline | Stateful workflow that retrieves recipes, checks relevance, checks allergens, routes unsafe recipes to the Substitution Agent, generates a grounded answer, and runs hallucination checks. |
| Substitution Agent | Specialist agent that chooses the best context-aware substitute for unsafe ingredients and verifies substitute safety. |
| Grocery Agent | Turns a selected recipe into a grocery plan; deterministic tools compute pantry diff, safety checks, substitutions, and cart draft contents. |
| Deterministic tools | Pantry diff, allergen triage, substitute safety backstops, cart assembly, and profile storage. |

This design makes the system agentic because it observes intermediate results, chooses tools, branches based on checks, retries failed steps, and stops safely when confidence is too low. The LLMs are not just writing text; they are participating in a controlled workflow with state, tools, routing, and explicit success/failure paths.

## Architecture Change: What Changed And Why

The project moved away from the earlier architecture where the recipe RAG graph carried most of the application logic. That earlier version was useful for proving retrieval, chunking, allergen metadata, and grounded recipe generation, but it was too narrow for the full product workflow.

The new architecture adds a top-level Meal Orchestrator and specialist agents around the RAG pipeline. This was needed because the user workflow expanded from a structured ingredient box to a chat-based meal-planning assistant: understand the user's intent, recommend recipes, repair unsafe recipes with substitutions, compare a selected recipe against pantry state, and prepare a grocery/cart draft with human approval.

The key design change is that RAG is now one capability inside a broader agentic system. Recipe retrieval remains important, but the application also needs routing, tool use, memory, substitution reasoning, grocery planning, and approval boundaries.

## Why The New Architecture Is Better

The refactor gives each part of the system a smaller, clearer job. The Meal Orchestrator owns intent routing but no domain logic. The Recipe Recommender owns recipe search but delegates safety and retrieval to the graph. The graph owns the control flow for unsafe recipes, while the Substitution Agent owns context-aware substitute choice and safety verification. The Grocery Agent owns pantry-to-cart planning, with deterministic tools computing the facts and the UI keeping final approval with the human.

This makes the demo stronger because the system can show real agentic behavior across multiple steps. A user can ask a normal meal-planning question in chat, and the system can move from intent routing to recipe search, substitutions, and grocery planning without pretending that one prompt or one model call can safely handle the entire workflow.

It also improves safety. Anything safety-critical is either deterministic or checked by deterministic backstops: allergen detection, pantry diff, substitute filtering, and final cart approval. The LLM is used where language and judgement matter, while hard facts and write actions remain controlled.

## What RAG Does In This System

RAG is still central, but it is no longer the whole architecture. The recipe pipeline uses Pinecone hybrid retrieval to find relevant recipe chunks, then LangGraph runs relevance checks, allergen checks, routes unsafe recipes to the Substitution Agent, performs generation, and runs hallucination checks.

In other words, the RAG pipeline is the Recipe Recommender's tool for answering chat requests like "what can I cook with chicken, garlic, and tomatoes?" The broader agentic system decides when to call it, how to use its result, and what downstream action should happen next.

## State And Memory

AlloChef uses persistent and runtime memory separately. Persistent state lives in SQLite and stores family profiles, allergen preferences, and pantry items across sessions. Runtime state lives in LangGraph and stores the current meal request: ingredients, active restrictions, retrieved recipes, unsafe recipe pairs, substitutions, relevance verdicts, hallucination verdicts, and final response.

This separation matters because family profiles and pantry data should survive across sessions, while retrieval results and generation attempts only matter for the current request.

The Meal Orchestrator and specialist agents also pass structured results through controlled state rather than relying only on conversation history. This lets the UI render recipe cards, substitution cards, and grocery plans from actual structured data instead of trying to scrape them from free-form text.

## Human Approval Boundary

All read and recommendation actions can run autonomously: image scanning, recipe retrieval, allergen checks, substitution lookup, pantry comparison, and recipe generation. Any action that creates or modifies something consequential is human-gated. In this project, the key write-style action is grocery/cart creation, which requires the user to review and approve the draft before proceeding.

This boundary is deliberate: reads and analysis can be automated, but actions that affect the user's shopping flow require explicit approval.

"""
Seed predefined role-play scenarios.

Run:  python -m app.scripts.seed_scenarios
"""

import asyncio

from sqlalchemy import select

from app.core.database import async_session
from app.models.roleplay import RoleplayScenario

SCENARIOS = [
    {
        "title": "Job Interview",
        "description": "Practice answering common job interview questions with a hiring manager.",
        "category": "professional",
        "ai_role": "Hiring Manager",
        "user_role": "Candidate",
        "difficulty": "intermediate",
        "language": "en",
        "starting_prompt": "Welcome to the interview. Please introduce yourself and tell me about your background.",
        "expected_topics": ["experience", "strengths", "weaknesses", "career goals", "teamwork"],
    },
    {
        "title": "Customer Support Call",
        "description": "Handle a customer complaint about a product or service issue.",
        "category": "professional",
        "ai_role": "Upset Customer",
        "user_role": "Support Agent",
        "difficulty": "advanced",
        "language": "en",
        "starting_prompt": "Hi, I need to speak with someone. I've been waiting for my refund for two weeks and nobody has helped me!",
        "expected_topics": ["empathy", "problem solving", "policy explanation", "resolution"],
    },
    {
        "title": "Ordering Food at a Restaurant",
        "description": "Practice ordering a meal, asking about the menu, and making special requests.",
        "category": "daily_life",
        "ai_role": "Waiter",
        "user_role": "Customer",
        "difficulty": "beginner",
        "language": "en",
        "starting_prompt": "Good evening! Welcome to The Golden Fork. Here's our menu. Can I start you off with something to drink?",
        "expected_topics": ["menu items", "preferences", "allergies", "ordering", "payment"],
    },
    {
        "title": "Business Meeting",
        "description": "Lead or participate in a team meeting to discuss a project update.",
        "category": "professional",
        "ai_role": "Project Stakeholder",
        "user_role": "Project Manager",
        "difficulty": "advanced",
        "language": "en",
        "starting_prompt": "Good morning everyone. Let's get started. Can you give us an update on the project timeline and any blockers?",
        "expected_topics": ["progress update", "timeline", "risks", "next steps", "budget"],
    },
    {
        "title": "College Presentation Q&A",
        "description": "Answer questions from the audience after delivering a class presentation.",
        "category": "academic",
        "ai_role": "Professor & Students",
        "user_role": "Presenter",
        "difficulty": "intermediate",
        "language": "en",
        "starting_prompt": "Thank you for your presentation. I have a few questions. First, can you elaborate on the methodology you chose?",
        "expected_topics": ["methodology", "findings", "limitations", "future work", "references"],
    },
    {
        "title": "Friendly Conversation",
        "description": "Have a casual chat about hobbies, weekend plans, and interests.",
        "category": "casual",
        "ai_role": "Friend",
        "user_role": "Friend",
        "difficulty": "beginner",
        "language": "en",
        "starting_prompt": "Hey! It's been a while. How have you been? Done anything fun recently?",
        "expected_topics": ["hobbies", "weekend plans", "movies", "travel", "food"],
    },
]


async def seed():
    async with async_session() as db:
        existing = await db.execute(select(RoleplayScenario.title))
        existing_titles = {row[0] for row in existing.all()}

        added = 0
        for sc_data in SCENARIOS:
            if sc_data["title"] in existing_titles:
                continue
            db.add(RoleplayScenario(**sc_data))
            added += 1

        await db.commit()
        print(f"Seeded {added} new scenarios ({len(existing_titles)} already existed)")


if __name__ == "__main__":
    asyncio.run(seed())

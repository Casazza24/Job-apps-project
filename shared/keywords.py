# To add more search keywords, just append to SEARCH_KEYWORDS.
# To restrict to specific internship types, edit INTERNSHIP_DOMAINS.

SEARCH_KEYWORDS = [
    # Data Science variants
    "data science intern",
    "data science internship",
    "data scientist intern",
    "junior data scientist",
    # Data Engineering variants
    "data engineer intern",
    "data engineering internship",
    "data engineering intern",
    "junior data engineer",
    # Software Engineering variants
    "software engineer intern",
    "software engineering internship",
    "SWE intern",
    "software developer intern",
    "backend intern",
    "python intern",
    "full stack intern",
    # AI/ML variants
    "AI intern",
    "ML intern",
    "machine learning intern",
    "machine learning internship",
    "artificial intelligence intern",
    "deep learning intern",
    "NLP intern",
    # Data Analytics variants
    "data analytics intern",
    "analytics internship",
    "analytics intern",
    "business intelligence intern",
    "BI intern",
    # General tech intern (broad net)
    "data intern",
    "research intern data",
]

# Used by the orchestrator to judge relevance — any internship touching these domains scores well
INTERNSHIP_DOMAINS = [
    "data science", "machine learning", "AI", "data engineering",
    "software engineering", "analytics", "data analysis", "Python",
    "SQL", "statistics", "deep learning", "NLP", "computer vision",
]

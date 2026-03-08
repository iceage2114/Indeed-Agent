# db/models.py - Job dataclass and schema

from dataclasses import dataclass, field
from typing import Optional
import hashlib


@dataclass
class Job:
    title: str
    company: str
    location: str
    description: str
    url: str
    date_posted: str
    field_label: str
    scraped_at: str
    easy_apply: bool = False
    applied: bool = False
    applied_at: str = ""
    id: str = field(init=False)

    def __post_init__(self):
        # Stable unique ID derived from the job URL
        self.id = hashlib.md5(self.url.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "date_posted": self.date_posted,
            "field": self.field_label,
            "scraped_at": self.scraped_at,
            "easy_apply": self.easy_apply,
            "applied": self.applied,
            "applied_at": self.applied_at,
        }

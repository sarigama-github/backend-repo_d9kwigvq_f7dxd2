"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Example schemas (retain for reference)

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# App-specific schemas

class Song(BaseModel):
    """
    Songs collection schema
    Collection name: "song"
    Stores trending songs and fetched lyrics
    """
    title: str = Field(..., description="Song title")
    artist: str = Field(..., description="Primary artist name")
    album: Optional[str] = Field(None, description="Album name if available")
    cover: Optional[str] = Field(None, description="Artwork URL")
    apple_url: Optional[str] = Field(None, description="Apple Music URL")
    preview_url: Optional[str] = Field(None, description="30s preview URL if available")
    lyrics: Optional[str] = Field(None, description="Fetched lyrics text")
    lyrics_source: Optional[str] = Field(None, description="Provider used to fetch lyrics")
    country: Optional[str] = Field("id", description="Market/country code for charts")
    lang: Optional[str] = Field("id", description="Language context for UI/lyrics")
    rank: Optional[int] = Field(None, description="Chart position when stored")
    tags: Optional[List[str]] = Field(default=None, description="Optional tags like 'trending', 'viral'")

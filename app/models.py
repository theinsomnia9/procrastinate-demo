from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base


class ChuckNorrisJoke(Base):
    """Model for caching Chuck Norris jokes from the API."""
    
    __tablename__ = "chuck_norris_jokes"
    
    id = Column(Integer, primary_key=True, index=True)
    joke_id = Column(String(50), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=True, index=True)
    joke_text = Column(Text, nullable=False)
    icon_url = Column(String(255), nullable=True)
    url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Add composite index for common queries
    __table_args__ = (
        Index('idx_category_created', 'category', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ChuckNorrisJoke(id={self.id}, joke_id={self.joke_id}, category={self.category})>"

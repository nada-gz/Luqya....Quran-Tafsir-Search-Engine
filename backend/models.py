from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional

class Surah(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    number: int = Field(index=True, unique=True)
    name_arabic: str
    name_english: str
    revelation_type: str
    
    ayahs: List["Ayah"] = Relationship(back_populates="surah")

class Ayah(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    surah_id: Optional[int] = Field(default=None, foreign_key="surah.id")
    ayah_number: int  # Ayah number within the surah
    text_uthmani: str # The arabic text
    category: Optional[str] = Field(default=None, index=True) # E.g., Patience
    
    surah: Optional[Surah] = Relationship(back_populates="ayahs")
    tafsirs: List["Tafsir"] = Relationship(back_populates="ayah")

class Tafsir(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    ayah_id: Optional[int] = Field(default=None, foreign_key="ayah.id")
    tafsir_type: str # 'simple_moyassar', 'simple_saadi', 'advanced_katheer', 'advanced_tabari'
    text: str
    
    ayah: Optional[Ayah] = Relationship(back_populates="tafsirs")

class Morphology(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    surah_number: int = Field(index=True)
    ayah_number: int = Field(index=True)
    word_number: int
    segment_number: int
    text: str
    root: Optional[str] = Field(default=None, index=True)
    lemma: Optional[str] = Field(default=None)


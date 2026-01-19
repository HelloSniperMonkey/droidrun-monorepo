"""Resume parser using AI to extract relevant information"""
import PyPDF2
import json
from typing import Dict, Optional
from pathlib import Path
import requests
import anthropic
from pydantic import BaseModel, Field
from job_hunter.config import Config


class ResumeData(BaseModel):
    """Structured resume data"""
    full_name: str = Field(description="Full name of the candidate")
    email: str = Field(description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    location: Optional[str] = Field(default=None, description="Current location")
    skills: list[str] = Field(default_factory=list, description="List of technical and soft skills")
    experience: list[Dict] = Field(default_factory=list, description="Work experience")
    education: list[Dict] = Field(default_factory=list, description="Education details")
    certifications: list[str] = Field(default_factory=list, description="Certifications")
    job_titles: list[str] = Field(default_factory=list, description="Relevant job titles/roles")
    years_of_experience: Optional[int] = Field(default=None, description="Total years of experience")
    preferred_roles: list[str] = Field(default_factory=list, description="Preferred job roles")
    summary: Optional[str] = Field(default=None, description="Professional summary")


class ResumeParser:
    """Parse resume PDF and extract structured information using AI"""

    def __init__(self):
        self.openrouter_api_key = Config.OPENROUTER_API_KEY
        self.anthropic_client = None

        if Config.ANTHROPIC_API_KEY:
            self.anthropic_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF resume"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

    def parse_with_openrouter(self, resume_text: str) -> ResumeData:
        """Parse resume using OpenRouter's free model (openai/gpt-oss-120b:free)"""
        if not self.openrouter_api_key:
            raise ValueError("OpenRouter API key not configured")

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/ai-job-hunter",
                    "X-Title": "AI Job Hunter"
                },
                data=json.dumps({
                    "model": Config.OPENROUTER_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are an expert resume parser. Extract all relevant information from the resume text.
                        Focus on: name, contact info, skills, work experience, education, certifications, and career preferences.
                        For experience, include company, role, duration, and responsibilities (as an array).
                        For education, include degree, institution, year (as integer), and major/field.

                        Return your response as a JSON object with these fields:
                        - full_name: string
                        - email: string
                        - phone: string or null
                        - location: string or null
                        - skills: array of strings
                        - experience: array of objects with {company: string, role: string, duration: string, responsibilities: array of strings}
                        - education: array of objects with {degree: string, institution: string, year: integer, major: string}
                        - certifications: array of strings
                        - job_titles: array of strings (relevant job titles from experience)
                        - years_of_experience: integer or null
                        - preferred_roles: array of strings (inferred from experience/skills)
                        - summary: string or null

                        Return ONLY the JSON object, no additional text."""
                        },
                        {
                            "role": "user",
                            "content": f"Parse this resume and extract structured information:\n\n{resume_text}"
                        }
                    ]
                })
            )

            response.raise_for_status()
            result = response.json()

            # Extract content from response
            content = result['choices'][0]['message']['content']

            # Parse JSON from response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            json_str = content[start_idx:end_idx]

            data = json.loads(json_str)
            return ResumeData(**data)
        except Exception as e:
            raise Exception(f"Failed to parse resume with OpenRouter: {str(e)}")

    def parse_with_anthropic(self, resume_text: str) -> ResumeData:
        """Parse resume using Anthropic Claude"""
        if not self.anthropic_client:
            raise ValueError("Anthropic API key not configured")

        try:
            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": f"""You are an expert resume parser. Extract all relevant information from this resume.

Resume text:
{resume_text}

Please extract and return a JSON object with the following fields:
- full_name: candidate's full name
- email: email address
- phone: phone number (if available)
- location: current location (if available)
- skills: array of technical and soft skills
- experience: array of objects with company, role, duration, responsibilities
- education: array of objects with degree, institution, year, major
- certifications: array of certification names
- job_titles: array of relevant job titles/roles from experience
- years_of_experience: total years of professional experience
- preferred_roles: array of preferred job roles (infer from experience and skills)
- summary: professional summary

Return ONLY the JSON object, no additional text."""
                    }
                ]
            )

            import json
            response_text = message.content[0].text
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            json_str = response_text[start_idx:end_idx]

            data = json.loads(json_str)
            return ResumeData(**data)
        except Exception as e:
            raise Exception(f"Failed to parse resume with Anthropic: {str(e)}")

    def parse_resume(self, pdf_path: str, use_anthropic: bool = False) -> ResumeData:
        """
        Parse resume PDF and extract structured information

        Args:
            pdf_path: Path to the resume PDF file
            use_anthropic: Use Anthropic Claude instead of OpenAI (default: False)

        Returns:
            ResumeData: Structured resume information
        """
        # Extract text from PDF
        resume_text = self.extract_text_from_pdf(pdf_path)

        if not resume_text:
            raise ValueError("No text could be extracted from the PDF")

        # Parse with AI
        if use_anthropic or (not self.openrouter_api_key and self.anthropic_client):
            return self.parse_with_anthropic(resume_text)
        else:
            return self.parse_with_openrouter(resume_text)

    def generate_search_keywords(self, resume_data: ResumeData) -> list[str]:
        """Generate search keywords for job hunting based on resume"""
        keywords = []

        # Add job titles
        keywords.extend(resume_data.job_titles)

        # Add preferred roles
        keywords.extend(resume_data.preferred_roles)

        # Add top skills
        keywords.extend(resume_data.skills[:10])  # Top 10 skills

        # Remove duplicates and return
        return list(set(keywords))

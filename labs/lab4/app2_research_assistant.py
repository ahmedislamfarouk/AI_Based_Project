import os
from typing import List, Dict
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.document_loaders import ArxivLoader
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

class AcademicResearchAssistant:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.1)
        self.wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        
    def _search_wikipedia(self, query: str) -> str:
        """Tool 1: Wikipedia Search."""
        return self.wiki.run(query)

    def _search_arxiv(self, query: str) -> List[Dict]:
        """Tool 2: ArXiv Academic Search."""
        docs = ArxivLoader(query=query, load_max_docs=3).load()
        results = []
        for doc in docs:
            results.append({
                "title": doc.metadata.get("Title", "N/A"),
                "summary": doc.page_content[:1000],
                "authors": doc.metadata.get("Authors", "N/A"),
                "url": doc.metadata.get("Entry ID", "N/A")
            })
        return results

    def _filter_relevance(self, query: str, resources: List[str]) -> List[str]:
        """Mechanism to filter for relevance (simplified)."""
        # In a real app, this could use an LLM or similarity scoring
        return [r for r in resources if len(r) > 100]

    def generate_research_report(self, topic: str):
        """Synthesize information into a structured report."""
        print(f"Researching: {topic}...")
        
        # Collect data
        wiki_data = self._search_wikipedia(topic)
        arxiv_data = self._search_arxiv(topic)
        
        # Synthesis Prompt
        template = """
        You are a PhD Academic Research Assistant. Synthesize the following information 
        into a structured formal report about '{topic}'.
        
        SOURCES FOUND:
        - Wikipedia Summary: {wiki}
        - ArXiv Papers: {arxiv}
        
        REQUIREMENTS:
        1. Introduction
        2. Key Findings
        3. Current Trends
        4. Citations & Sources (Tracking)
        
        Format the output in clean Markdown.
        """
        
        prompt = PromptTemplate(
            input_variables=["topic", "wiki", "arxiv"],
            template=template
        )
        
        chain = LLMChain(llm=self.llm, prompt=prompt)
        
        report = chain.invoke({
            "topic": topic,
            "wiki": wiki_data,
            "arxiv": str(arxiv_data)
        })
        
        return report["text"]

if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = "your-api-key-here"
    assistant = AcademicResearchAssistant()
    final_report = assistant.generate_research_report("Quantum Computing Ethics")
    
    with open("research_report.md", "w") as f:
        f.write(final_report)
    print("Report generated successfully.")

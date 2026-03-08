import os
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.document_loaders import ArxivLoader
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# 1. Tools
wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
arxiv = lambda q: ArxivLoader(query=q, load_max_docs=2).load()

# 2. Synthesis Logic
def research(topic):
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    data = f"WIKI: {wiki.run(topic)}\nARXIV: {arxiv(topic)}"
    
    prompt = PromptTemplate.from_template("Synthesize into a formal report with citations: {data}")
    return llm.predict(prompt.format(data=data))

if __name__ == "__main__":
    print(research("AI in healthcare"))

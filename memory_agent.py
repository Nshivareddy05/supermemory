import subprocess
import chromadb
from sentence_transformers import SentenceTransformer
import uuid
import argparse
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

class SentenceTransformerEmbeddingFunction(chromadb.EmbeddingFunction):
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: chromadb.Documents):
        return self.model.encode(list(input)).tolist()

class LocalMemorySystem:
    def __init__(self, db_path="./ai_memory", collection_name="conversations", threshold=0.3):
        self.client = chromadb.PersistentClient(path=db_path)
        self.embedding_fn = SentenceTransformerEmbeddingFunction()
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name, 
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        
        # New: Facts collection for specific user-defined QA pairs
        self.facts_collection = self.client.get_or_create_collection(
            name="facts",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        
        self.threshold = threshold

    def fallback_keyword_extraction(self, text: str) -> str:
        words = [w.lower() for w in text.split() if w.isalnum() and len(w) > 4]
        return " ".join(set(words))[:200]

    def _call_ollama(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                ["ollama", "run", "mistral"],
                input=prompt.encode('utf-8'),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return result.stdout.decode('utf-8').strip()
        except subprocess.CalledProcessError as e:
            return f"Error: Ollama failed. {e.stderr.decode('utf-8')}"
        except FileNotFoundError:
            return "Error: Ollama is not installed or not in PATH."

    def add_fact(self, question: str, answer: str) -> None:
        """Adds a specific fact to the database."""
        self.facts_collection.add(
            documents=[question],
            metadatas=[{"answer": answer}],
            ids=[str(uuid.uuid4())]
        )

    def get_all_facts(self) -> list:
        """Retrieves all facts."""
        results = self.facts_collection.get()
        facts = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"]):
                facts.append({
                    "id": results["ids"][i],
                    "question": doc,
                    "answer": results["metadatas"][i]["answer"]
                })
        return facts
        
    def delete_fact(self, fact_id: str) -> None:
        """Deletes a fact by ID."""
        self.facts_collection.delete(ids=[fact_id])

    def query(self, prompt: str) -> dict:
        # 1. Search Facts first (prioritize exact/close matches)
        fact_results = self.facts_collection.query(
            query_texts=[prompt],
            n_results=1
        )
        
        if fact_results and fact_results['distances'] and len(fact_results['distances'][0]) > 0:
            distance = fact_results['distances'][0][0]
            if distance <= self.threshold:
                return {
                    "response": fact_results['metadatas'][0][0]['answer'],
                    "source": "fact",
                    "distance": distance
                }

        # 2. Search Conversation Cache
        results = self.collection.query(
            query_texts=[prompt],
            n_results=1
        )

        if results and results['distances'] and len(results['distances'][0]) > 0:
            distance = results['distances'][0][0]
            if distance <= self.threshold:
                return {
                    "response": results['metadatas'][0][0]['response'],
                    "source": "memory",
                    "distance": distance
                }
        
        response = self._call_ollama(prompt)
        keywords = self.fallback_keyword_extraction(prompt)
        
        self.collection.add(
            documents=[prompt],
            metadatas=[{"response": response, "keywords": keywords}],
            ids=[str(uuid.uuid4())]
        )
        
        return {
            "response": response,
            "source": "ollama",
            "distance": None
        }

    def export_data(self) -> dict:
        """Exports Chromadb facts and conversations."""
        return {
            "facts": self.get_all_facts(),
            "conversations": self.collection.get()
        }

    def import_data(self, data: dict) -> None:
        """Imports Chromadb facts and conversations."""
        if "facts" in data:
            for fact in data["facts"]:
                try:
                    self.facts_collection.add(
                        documents=[fact["question"]],
                        metadatas=[{"answer": fact["answer"]}],
                        ids=[fact["id"]]
                    )
                except Exception:
                    pass # Ignore if exists

        if "conversations" in data:
            convs = data["conversations"]
            if convs and convs.get("documents"):
                # We can't insert all at once easily due to existing ones potentially throwing errors
                for i, doc in enumerate(convs["documents"]):
                    try:
                        self.collection.add(
                            documents=[doc],
                            metadatas=[convs["metadatas"][i]],
                            ids=[convs["ids"][i]]
                        )
                    except Exception:
                        pass # Ignore if exists

def main():
    parser = argparse.ArgumentParser(description="Local AI Memory System CLI")
    parser.add_argument("--threshold", type=float, default=0.3, help="Cosine distance similarity threshold")
    args = parser.parse_args()

    console.print(Panel.fit("[bold violet]Onyx AI Memory System[/bold violet]\nPowered by Mistral, ChromaDB & Rich", border_style="violet"))
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Initializing Memory System...", total=None)
        system = LocalMemorySystem(threshold=args.threshold)
        
    console.print("[green]System Ready. Type 'exit' or 'quit' to quit.[/green]\n")
    
    while True:
        try:
            user_input = console.input("[bold cyan]User>[/bold cyan] ").strip()
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input:
                continue
                
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
                progress.add_task(description="Thinking...", total=None)
                result = system.query(user_input)
            
            source = result.get('source', '')
            response_text = result['response']
            
            if source == "fact":
                console.print(f"[bold green]⚡ Retrieved from Facts DB (distance: {result['distance']:.4f})[/bold green]")
            elif source == "memory":
                console.print(f"[bold yellow]⚡ Retrieved from Memory Cache (distance: {result['distance']:.4f})[/bold yellow]")
            else:
                console.print("[dim]🧠 Generated by Mistral[/dim]")
                
            console.print(Panel(Markdown(response_text), title="AI", title_align="left", border_style="cyan"))
            
        except KeyboardInterrupt:
            console.print("\n[red]Exiting...[/red]")
            break
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}[/bold red]")

if __name__ == "__main__":
    main()

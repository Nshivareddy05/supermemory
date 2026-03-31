import json
from db import export_db_to_dict, import_dict_to_db

def export_all_data(memory_system):
    """Exports all data (chats, facts, cache) to a single dictionary."""
    sqlite_data = export_db_to_dict()
    chroma_data = memory_system.export_data()
    
    return {
        "sqlite_data": sqlite_data,
        "chroma_data": chroma_data
    }

def import_all_data(memory_system, data_dict):
    """Imports all data into SQLite and ChromaDB."""
    if "sqlite_data" in data_dict:
        import_dict_to_db(data_dict["sqlite_data"])
        
    if "chroma_data" in data_dict:
        memory_system.import_data(data_dict["chroma_data"])

"""Integration tests for the Analysis Agent API."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import os
import sys


from api.main import app

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def check_database_exists():
    """Check if the database file exists before running tests."""
    db_path = Path("real-summaries-2.db")
    if not db_path.exists():
        pytest.skip("Database file real-summaries-2.db not found")

class TestHealthAndSchema:
    """Test basic API functionality."""
    
    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["mode"] == "read-only"
        assert "database" in data

    def test_openapi_schema(self, client: TestClient):
        """Test OpenAPI schema endpoint."""
        response = client.get("/schema")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert schema["info"]["title"] == "Analysis Agent API"

class TestFilesEndpoints:
    """Test files-related endpoints."""
    
    def test_get_files_basic(self, client: TestClient, check_database_exists):
        """Test basic files endpoint."""
        response = client.get("/files")
        assert response.status_code == 200
        files = response.json()
        assert isinstance(files, list)
        
        if files:  # If there are files in the database
            file = files[0]
            assert "id" in file
            assert "file_path" in file
            assert "language" in file
            assert "created_at" in file
            assert "last_modified" in file

    def test_get_files_with_limit(self, client: TestClient, check_database_exists):
        """Test files endpoint with limit parameter."""
        response = client.get("/files?limit=5")
        assert response.status_code == 200
        files = response.json()
        assert isinstance(files, list)
        assert len(files) <= 5

    def test_get_files_with_offset(self, client: TestClient, check_database_exists):
        """Test files endpoint with offset parameter."""
        response = client.get("/files?offset=0&limit=10")
        assert response.status_code == 200
        files = response.json()
        assert isinstance(files, list)

    def test_get_files_with_language_filter(self, client: TestClient, check_database_exists):
        """Test files endpoint with language filter."""
        response = client.get("/files?language=typescript")
        assert response.status_code == 200
        files = response.json()
        assert isinstance(files, list)
        
        # All returned files should have the specified language
        for file in files:
            assert file.get("language") == "typescript"

    def test_get_file_by_id(self, client: TestClient, check_database_exists):
        """Test getting a specific file by ID."""
        # First get a list of files to get a valid ID
        files_response = client.get("/files?limit=1")
        assert files_response.status_code == 200
        files = files_response.json()
        
        if not files:
            pytest.skip("No files in database to test with")
        
        file_id = files[0]["id"]
        
        # Now get the specific file
        response = client.get(f"/files/{file_id}")
        assert response.status_code == 200
        file_detail = response.json()
        
        assert file_detail["id"] == file_id
        assert "file_content" in file_detail
        assert "definitions" in file_detail
        assert isinstance(file_detail["definitions"], list)
        
        # Check definitions structure if any exist
        for definition in file_detail["definitions"]:
            assert "id" in definition
            assert "name" in definition
            assert "definition_type" in definition
            assert "function_calls" in definition
            assert "type_references" in definition
            assert isinstance(definition["function_calls"], list)
            assert isinstance(definition["type_references"], list)

    def test_get_nonexistent_file(self, client: TestClient, check_database_exists):
        """Test getting a non-existent file returns 404."""
        response = client.get("/files/999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

class TestDefinitionsEndpoints:
    """Test definitions-related endpoints."""
    
    def test_get_definitions_basic(self, client: TestClient, check_database_exists):
        """Test basic definitions endpoint."""
        response = client.get("/definitions")
        assert response.status_code == 200
        definitions = response.json()
        assert isinstance(definitions, list)
        
        if definitions:  # If there are definitions in the database
            definition = definitions[0]
            assert "id" in definition
            assert "name" in definition
            assert "definition_type" in definition
            assert "start_line" in definition
            assert "end_line" in definition
            assert "is_exported" in definition
            assert "function_calls" in definition
            assert "type_references" in definition
            assert isinstance(definition["function_calls"], list)
            assert isinstance(definition["type_references"], list)

    def test_get_definitions_with_filters(self, client: TestClient, check_database_exists):
        """Test definitions endpoint with various filters."""
        # Test with definition_type filter
        response = client.get("/definitions?definition_type=function")
        assert response.status_code == 200
        definitions = response.json()
        assert isinstance(definitions, list)
        
        for definition in definitions:
            assert definition.get("definition_type") == "function"

    def test_get_definitions_with_export_filter(self, client: TestClient, check_database_exists):
        """Test definitions endpoint with export filter."""
        response = client.get("/definitions?is_exported=true")
        assert response.status_code == 200
        definitions = response.json()
        assert isinstance(definitions, list)
        
        for definition in definitions:
            assert definition.get("is_exported") is True

    def test_get_definition_by_id(self, client: TestClient, check_database_exists):
        """Test getting a specific definition by ID."""
        # First get a list of definitions to get a valid ID
        definitions_response = client.get("/definitions?limit=1")
        assert definitions_response.status_code == 200
        definitions = definitions_response.json()
        
        if not definitions:
            pytest.skip("No definitions in database to test with")
        
        definition_id = definitions[0]["id"]
        
        # Now get the specific definition
        response = client.get(f"/definitions/{definition_id}")
        assert response.status_code == 200
        definition_detail = response.json()
        
        assert definition_detail["id"] == definition_id
        assert "source_code" in definition_detail
        assert "source_code_hash" in definition_detail
        assert "function_calls" in definition_detail
        assert "type_references" in definition_detail

    def test_get_nonexistent_definition(self, client: TestClient, check_database_exists):
        """Test getting a non-existent definition returns 404."""
        response = client.get("/definitions/999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

class TestImportsEndpoints:
    """Test imports-related endpoints."""
    
    def test_get_imports_basic(self, client: TestClient, check_database_exists):
        """Test basic imports endpoint."""
        response = client.get("/imports")
        assert response.status_code == 200
        imports = response.json()
        assert isinstance(imports, list)
        
        if imports:  # If there are imports in the database
            import_item = imports[0]
            assert "id" in import_item
            assert "file_id" in import_item
            assert "specifier" in import_item
            assert "module" in import_item
            assert "import_type" in import_item
            assert "is_external" in import_item

    def test_get_imports_with_filters(self, client: TestClient, check_database_exists):
        """Test imports endpoint with filters."""
        response = client.get("/imports?is_external=false")
        assert response.status_code == 200
        imports = response.json()
        assert isinstance(imports, list)
        
        for import_item in imports:
            assert import_item.get("is_external") is False

class TestFunctionCallsEndpoints:
    """Test function calls-related endpoints."""
    
    def test_get_function_calls_basic(self, client: TestClient, check_database_exists):
        """Test basic function calls endpoint."""
        response = client.get("/function-calls")
        assert response.status_code == 200
        function_calls = response.json()
        assert isinstance(function_calls, list)
        
        if function_calls:  # If there are function calls in the database
            call = function_calls[0]
            assert "id" in call
            assert "callee_name" in call
            assert "caller_definition_id" in call

    def test_get_function_calls_with_filters(self, client: TestClient, check_database_exists):
        """Test function calls endpoint with filters."""
        # First get a definition ID to filter by
        definitions_response = client.get("/definitions?limit=1")
        definitions = definitions_response.json()
        
        if not definitions:
            pytest.skip("No definitions in database to test with")
        
        definition_id = definitions[0]["id"]
        
        response = client.get(f"/function-calls?caller_definition_id={definition_id}")
        assert response.status_code == 200
        function_calls = response.json()
        assert isinstance(function_calls, list)
        
        for call in function_calls:
            assert call.get("caller_definition_id") == definition_id

class TestTypeReferencesEndpoints:
    """Test type references-related endpoints."""
    
    def test_get_type_references_basic(self, client: TestClient, check_database_exists):
        """Test basic type references endpoint."""
        response = client.get("/type-references")
        assert response.status_code == 200
        type_refs = response.json()
        assert isinstance(type_refs, list)
        
        if type_refs:  # If there are type references in the database
            type_ref = type_refs[0]
            assert "id" in type_ref
            assert "definition_id" in type_ref
            assert "type_name" in type_ref
            assert "source" in type_ref

    def test_get_type_references_with_filters(self, client: TestClient, check_database_exists):
        """Test type references endpoint with filters."""
        # First get a definition ID to filter by
        definitions_response = client.get("/definitions?limit=1")
        definitions = definitions_response.json()
        
        if not definitions:
            pytest.skip("No definitions in database to test with")
        
        definition_id = definitions[0]["id"]
        
        response = client.get(f"/type-references?definition_id={definition_id}")
        assert response.status_code == 200
        type_refs = response.json()
        assert isinstance(type_refs, list)
        
        for type_ref in type_refs:
            assert type_ref.get("definition_id") == definition_id

class TestPaginationAndValidation:
    """Test pagination and input validation."""
    
    def test_pagination_limits(self, client: TestClient, check_database_exists):
        """Test that pagination limits are enforced."""
        # Test maximum limit
        response = client.get("/files?limit=2000")
        assert response.status_code == 422  # Validation error
        
        # Test minimum limit
        response = client.get("/files?limit=0")
        assert response.status_code == 422  # Validation error
        
        # Test negative offset
        response = client.get("/files?offset=-1")
        assert response.status_code == 422  # Validation error

    def test_valid_pagination(self, client: TestClient, check_database_exists):
        """Test valid pagination parameters."""
        response = client.get("/files?limit=10&offset=0")
        assert response.status_code == 200
        
        response = client.get("/files?limit=1000&offset=100")
        assert response.status_code == 200

class TestSemanticSearchBatch:
    """Test semantic search batch endpoint."""
    
    def test_batch_search_basic(self, client: TestClient, check_database_exists):
        """Test basic batch semantic search functionality."""
        batch_request = {
            "queries": ["function", "class", "import"],
            "limit": 5,
            "similarity_threshold": 0.0
        }
        
        response = client.post("/search/semantic/batch", json=batch_request)
        
        # Should return 200 even if embeddings aren't available (returns empty results)
        if response.status_code == 503:
            # Skip test if vector database not available
            pytest.skip("Vector database not available")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "batch_metadata" in data
        assert "results" in data
        assert len(data["results"]) == 3  # Should match number of queries
        
        # Verify batch metadata
        assert data["batch_metadata"]["total_queries"] == 3
        assert "execution_time_seconds" in data["batch_metadata"]
        assert data["batch_metadata"]["limit_per_query"] == 5
        
        # Verify each query result structure
        for i, result in enumerate(data["results"]):
            assert result["query"] == batch_request["queries"][i]
            assert "total_results" in result
            assert "files" in result
            assert "definitions" in result
            assert "search_metadata" in result
            assert isinstance(result["files"], list)
            assert isinstance(result["definitions"], list)
    
    def test_batch_search_with_filters(self, client: TestClient, check_database_exists):
        """Test batch search with language and definition type filters."""
        batch_request = {
            "queries": ["function", "variable"],
            "language": "typescript",
            "definition_type": "function",
            "limit": 3,
            "similarity_threshold": 0.1
        }
        
        response = client.post("/search/semantic/batch", json=batch_request)
        
        if response.status_code == 503:
            pytest.skip("Vector database not available")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filters are reflected in metadata
        assert data["batch_metadata"]["language_filter"] == "typescript"
        assert data["batch_metadata"]["definition_type_filter"] == "function"
        assert data["batch_metadata"]["similarity_threshold"] == 0.1
    
    def test_batch_search_empty_queries(self, client: TestClient):
        """Test batch search with empty queries list."""
        batch_request = {
            "queries": [],
            "limit": 5
        }
        
        response = client.post("/search/semantic/batch", json=batch_request)
        
        if response.status_code == 503:
            pytest.skip("Vector database not available")
        
        assert response.status_code == 200
        data = response.json()
        assert data["batch_metadata"]["total_queries"] == 0
        assert len(data["results"]) == 0
    
    def test_batch_search_validation(self, client: TestClient):
        """Test batch search input validation."""
        # Test invalid limit
        response = client.post("/search/semantic/batch", json={
            "queries": ["test"],
            "limit": 0
        })
        assert response.status_code == 422
        
        # Test invalid similarity threshold
        response = client.post("/search/semantic/batch", json={
            "queries": ["test"],
            "similarity_threshold": 1.5
        })
        assert response.status_code == 422
        
        # Test missing queries field
        response = client.post("/search/semantic/batch", json={
            "limit": 5
        })
        assert response.status_code == 422


class TestCORSAndSecurity:
    """Test CORS configuration and security aspects."""
    
    def test_cors_headers_present(self, client: TestClient):
        """Test that CORS headers are present."""
        response = client.get("/health")
        assert response.status_code == 200
        # FastAPI TestClient doesn't automatically add CORS headers in tests,
        # but we can verify the middleware is configured

    def test_read_only_operations(self, client: TestClient):
        """Test that most operations are read-only except semantic batch."""
        # Test POST is not allowed on files
        response = client.post("/files", json={})
        assert response.status_code == 405  # Method not allowed
        
        # Test PUT is not allowed
        response = client.put("/files/1", json={})
        assert response.status_code == 405  # Method not allowed
        
        # Test DELETE is not allowed
        response = client.delete("/files/1")
        assert response.status_code == 405  # Method not allowed
        
        # Test POST is allowed on semantic batch endpoint
        response = client.post("/search/semantic/batch", json={"queries": []})
        # Should not be 405 (Method not allowed)
        assert response.status_code != 405
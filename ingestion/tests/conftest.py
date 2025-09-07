"""Shared pytest fixtures for testing."""

import pytest

from database.manager import DatabaseManager, session_scope
from database.models import (
    FileModel,
    DefinitionModel,
    ImportModel,
    ReferenceModel,
)


@pytest.fixture
def db_manager():
    """Create an in-memory database manager for testing."""
    return DatabaseManager(db_path=":memory:", echo=False, expire_on_commit=False)


@pytest.fixture
def sample_file(db_manager):
    """Create a sample FileModel for testing."""
    with session_scope(db_manager) as session:
        file_model = FileModel(
            file_path="test/calculator.ts",
            file_content="""
import { MathUtils } from './utils';

export function add(a: number, b: number): number {
    return a + b;
}

export function multiply(x: number, y: number): number {
    return MathUtils.multiply(x, y);
}

export class Calculator {
    private history: number[] = [];
    
    calculate(operation: string, a: number, b: number): number {
        let result: number;
        switch (operation) {
            case 'add':
                result = add(a, b);
                break;
            case 'multiply':
                result = multiply(a, b);
                break;
            default:
                throw new Error('Unknown operation');
        }
        this.history.push(result);
        return result;
    }
}
""",
            language="typescript",
        )

        session.add(file_model)
        session.flush()
        return file_model


@pytest.fixture
def sample_definitions(db_manager, sample_file: FileModel):
    """Create sample DefinitionModel instances for testing."""
    with session_scope(db_manager) as session:
        definitions = []

        # Add function definition
        add_func = DefinitionModel(
            name="add",
            definition_type="function",
            start_line=4,
            end_line=6,
            source_code="export function add(a: number, b: number): number {\n    return a + b;\n}",
            is_exported=True,
            complexity_score=1,
            docstring=None,
            source_code_hash="add_hash",
        )
        add_func.file = sample_file

        # Multiply function definition
        multiply_func = DefinitionModel(
            name="multiply",
            definition_type="function",
            start_line=8,
            end_line=10,
            source_code="export function multiply(x: number, y: number): number {\n    return MathUtils.multiply(x, y);\n}",
            is_exported=True,
            complexity_score=2,
            docstring=None,
            source_code_hash="multiply_hash",
        )
        multiply_func.file = sample_file

        # Calculator class definition
        calculator_class = DefinitionModel(
            name="Calculator",
            definition_type="class",
            start_line=12,
            end_line=28,
            source_code="""export class Calculator {
    private history: number[] = [];
    
    calculate(operation: string, a: number, b: number): number {
        let result: number;
        switch (operation) {
            case 'add':
                result = add(a, b);
                break;
            case 'multiply':
                result = multiply(a, b);
                break;
            default:
                throw new Error('Unknown operation');
        }
        this.history.push(result);
        return result;
    }
}""",
            is_exported=True,
            complexity_score=5,
            docstring="A calculator class that performs basic arithmetic operations and maintains history.",
            source_code_hash="calculator_hash",
        )
        calculator_class.file = sample_file

        # Calculate method definition (nested in class)
        calculate_method = DefinitionModel(
            name="calculate",
            definition_type="function",
            start_line=15,
            end_line=27,
            source_code="""calculate(operation: string, a: number, b: number): number {
        let result: number;
        switch (operation) {
            case 'add':
                result = add(a, b);
                break;
            case 'multiply':
                result = multiply(a, b);
                break;
            default:
                throw new Error('Unknown operation');
        }
        this.history.push(result);
        return result;
    }""",
            is_exported=False,
            complexity_score=4,
            docstring=None,
            source_code_hash="calculate_hash",
        )
        calculate_method.file = sample_file

        definitions = [add_func, multiply_func, calculator_class, calculate_method]

        for definition in definitions:
            session.add(definition)

        session.flush()
        return definitions


@pytest.fixture
def sample_function_calls(db_manager, sample_definitions):
    """Create sample FunctionCallModel instances for testing."""
    with session_scope(db_manager) as session:
        add_func, multiply_func, calculator_class, calculate_method = sample_definitions

        function_calls = []

        # calculate method calls add function
        call_add = ReferenceModel(
            reference_name="add",
            reference_type="local",
            source_definition=calculate_method,
        )
        call_add.target_definition = add_func

        # calculate method calls multiply function
        call_multiply = ReferenceModel(
            reference_name="multiply",
            reference_type="local",
            source_definition=calculate_method,
        )
        call_multiply.target_definition = multiply_func

        # multiply function calls external MathUtils.multiply
        call_math_utils = ReferenceModel(
            reference_name="MathUtils.multiply",
            reference_type="imported",
            source_definition=multiply_func,
        )

        function_calls = [call_add, call_multiply, call_math_utils]

        for call in function_calls:
            session.add(call)

        session.flush()
        return function_calls


@pytest.fixture
def sample_type_references(db_manager, sample_definitions):
    """Create sample TypeReferenceModel instances for testing."""
    with session_scope(db_manager) as session:
        add_func, multiply_func, calculator_class, calculate_method = sample_definitions

        type_references = []

        # calculate method uses number type (built-in)
        type_number = ReferenceModel(
            reference_name="number",
            reference_type="local",
            source_definition=calculate_method,
        )

        # calculate method uses string type (built-in)
        type_string = ReferenceModel(
            reference_name="string",
            reference_type="local",
            source_definition=calculate_method,
        )

        # Calculator class uses number[] for history
        type_number_array = ReferenceModel(
            reference_name="number[]",
            reference_type="local",
            source_definition=calculator_class,
        )

        type_references = [type_number, type_string, type_number_array]

        for type_ref in type_references:
            session.add(type_ref)

        session.flush()
        return type_references


@pytest.fixture
def sample_imports(db_manager, sample_file):
    """Create sample ImportModel instances for testing."""
    with session_scope(db_manager) as session:
        imports = []

        # Import MathUtils from ./utils
        math_utils_import = ImportModel(
            specifier="MathUtils",
            module="./utils",
            import_type="named",
            resolved_file_path="test/utils.ts",
            is_external=False,
        )
        math_utils_import.file = sample_file

        imports = [math_utils_import]

        for import_model in imports:
            session.add(import_model)

        session.flush()
        return imports


@pytest.fixture
def dependency_file(db_manager):
    """Create a dependency file for testing file-level dependencies."""
    with session_scope(db_manager) as session:
        utils_file = FileModel(
            file_path="test/utils.ts",
            file_content="""
export class MathUtils {
    static multiply(x: number, y: number): number {
        return x * y;
    }
    
    static divide(x: number, y: number): number {
        if (y === 0) throw new Error('Division by zero');
        return x / y;
    }
}
""",
            language="typescript",
        )

        session.add(utils_file)
        session.flush()

        # Add definition for MathUtils class
        math_utils_class = DefinitionModel(
            name="MathUtils",
            definition_type="class",
            start_line=2,
            end_line=10,
            source_code="""export class MathUtils {
    static multiply(x: number, y: number): number {
        return x * y;
    }
    
    static divide(x: number, y: number): number {
        if (y === 0) throw new Error('Division by zero');
        return x / y;
    }
}""",
            is_exported=True,
            complexity_score=3,
            docstring=None,
            source_code_hash="mathutils_hash",
        )
        math_utils_class.file = utils_file

        # Add multiply method
        multiply_method = DefinitionModel(
            name="multiply",
            definition_type="function",
            start_line=3,
            end_line=5,
            source_code="static multiply(x: number, y: number): number {\n        return x * y;\n    }",
            is_exported=False,
            complexity_score=1,
            docstring=None,
            source_code_hash="multiply_method_hash",
        )
        multiply_method.file = utils_file

        session.add(math_utils_class)
        session.add(multiply_method)
        session.flush()

        return utils_file


@pytest.fixture
def processing_order(
    db_manager,
    sample_file,
    sample_definitions,
    sample_function_calls,
    sample_type_references,
    sample_imports,
    dependency_file,
):
    """Fixture that provides test data and returns files in processing order (simulating topological sort)."""
    with session_scope(db_manager) as session:
        # Update the import to point to the dependency file
        math_utils_import = sample_imports[0]
        math_utils_import.resolved_file_path = dependency_file.file_path

        # Link function calls to their actual definitions
        call_add, call_multiply, call_math_utils = sample_function_calls

        # Find the MathUtils multiply method in dependency file
        math_utils_multiply = (
            session.query(DefinitionModel)
            .filter(
                DefinitionModel.file.has(file_path=dependency_file.file_path),
                DefinitionModel.name == "multiply",
            )
            .first()
        )

        if math_utils_multiply:
            call_math_utils.callee_definition = math_utils_multiply

        session.flush()

        # Return files in dependency order (dependencies first)
        return [dependency_file, sample_file]


@pytest.fixture
def parallel_test_structure(db_manager):
    """Create a multi-file, multi-definition structure for testing parallel processing.
    
    Creates a dependency structure with multiple levels:
    - Level 0 (no deps): base_utils.ts -> UtilsA, UtilsB  
    - Level 1 (depends on L0): mid_layer.ts -> ServiceA (uses UtilsA), ServiceB (uses UtilsB)
    - Level 2 (depends on L1): top_layer.ts -> MainApp (uses ServiceA, ServiceB)
    
    This structure allows testing parallel processing at each level.
    """
    with session_scope(db_manager) as session:
        # Level 0: Base utilities (no dependencies)
        base_utils_file = FileModel(
            file_path="test/base_utils.ts",
            file_content="""
export class UtilsA {
    static process(data: string): string {
        return data.toUpperCase();
    }
}

export class UtilsB {
    static transform(value: number): number {
        return value * 2;
    }
}
""",
            language="typescript",
        )
        session.add(base_utils_file)
        session.flush()

        # Create definitions for base utilities
        utils_a = DefinitionModel(
            name="UtilsA",
            definition_type="class", 
            start_line=2,
            end_line=6,
            source_code="export class UtilsA { static process(data: string): string { return data.toUpperCase(); } }",
            is_exported=True,
            complexity_score=1,
            docstring=None,
            source_code_hash="utils_a_hash",
        )
        utils_a.file = base_utils_file

        utils_b = DefinitionModel(
            name="UtilsB",
            definition_type="class",
            start_line=8,
            end_line=12, 
            source_code="export class UtilsB { static transform(value: number): number { return value * 2; } }",
            is_exported=True,
            complexity_score=1,
            docstring=None,
            source_code_hash="utils_b_hash",
        )
        utils_b.file = base_utils_file

        session.add(utils_a)
        session.add(utils_b)
        session.flush()

        # Level 1: Mid layer services (depend on base utilities)
        mid_layer_file = FileModel(
            file_path="test/mid_layer.ts", 
            file_content="""
import { UtilsA, UtilsB } from './base_utils';

export class ServiceA {
    processText(text: string): string {
        return UtilsA.process(text);
    }
}

export class ServiceB {
    processNumber(num: number): number {
        return UtilsB.transform(num);
    }
}
""",
            language="typescript",
        )
        session.add(mid_layer_file)
        session.flush()

        service_a = DefinitionModel(
            name="ServiceA",
            definition_type="class",
            start_line=4,
            end_line=8,
            source_code="export class ServiceA { processText(text: string): string { return UtilsA.process(text); } }",
            is_exported=True,
            complexity_score=2,
            docstring=None,
            source_code_hash="service_a_hash",
        )
        service_a.file = mid_layer_file

        service_b = DefinitionModel(
            name="ServiceB", 
            definition_type="class",
            start_line=10,
            end_line=14,
            source_code="export class ServiceB { processNumber(num: number): number { return UtilsB.transform(num); } }",
            is_exported=True,
            complexity_score=2,
            docstring=None,
            source_code_hash="service_b_hash",
        )
        service_b.file = mid_layer_file

        session.add(service_a)
        session.add(service_b)
        session.flush()

        # Level 2: Top layer (depends on mid layer services)
        top_layer_file = FileModel(
            file_path="test/top_layer.ts",
            file_content="""
import { ServiceA, ServiceB } from './mid_layer';

export class MainApp {
    process(text: string, num: number): {text: string, num: number} {
        const processedText = ServiceA.processText(text);
        const processedNum = ServiceB.processNumber(num);
        return { text: processedText, num: processedNum };
    }
}
""",
            language="typescript", 
        )
        session.add(top_layer_file)
        session.flush()

        main_app = DefinitionModel(
            name="MainApp",
            definition_type="class",
            start_line=4,
            end_line=10,
            source_code="""export class MainApp {
    process(text: string, num: number): {text: string, num: number} {
        const processedText = ServiceA.processText(text);
        const processedNum = ServiceB.processNumber(num);
        return { text: processedText, num: processedNum };
    }
}""",
            is_exported=True,
            complexity_score=3,
            docstring=None,
            source_code_hash="main_app_hash",
        )
        main_app.file = top_layer_file
        session.add(main_app)
        session.flush()

        # Create function calls to establish dependencies
        # ServiceA calls UtilsA.process
        call_utils_a = ReferenceModel(
            reference_name="UtilsA.process",
            source_definition=service_a,
            reference_type="imported",
            target_definition=utils_a,
        )

        # ServiceB calls UtilsB.transform  
        call_utils_b = ReferenceModel(
            reference_name="UtilsB.transform",
            source_definition=service_b,
            reference_type="imported",
            target_definition=utils_b,
        )

        # MainApp calls ServiceA.processText
        call_service_a = ReferenceModel(
            reference_name="ServiceA.processText",
            source_definition=main_app,
            reference_type="imported",
            target_definition=service_a,
        )

        # MainApp calls ServiceB.processNumber
        call_service_b = ReferenceModel(
            reference_name="ServiceB.processNumber",
            source_definition=main_app,
            reference_type="imported",
            target_definition=service_b,
        )

        session.add(call_utils_a)
        session.add(call_utils_b)
        session.add(call_service_a)
        session.add(call_service_b)
        session.flush()

        return {
            "files": [base_utils_file, mid_layer_file, top_layer_file],
            "definitions": {
                "level_0": [utils_a, utils_b],  # Can be processed in parallel
                "level_1": [service_a, service_b],  # Can be processed in parallel after level_0
                "level_2": [main_app],  # Must be processed after level_1
            }
        }


@pytest.fixture(autouse=True)
def clear_summary_caches():
    """Automatically clear summary caches before each test."""
    from ai_analysis.summaries import clear_summary_caches

    clear_summary_caches()
    yield
    clear_summary_caches()

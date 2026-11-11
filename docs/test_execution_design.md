# Enhanced Test Execution Data Flow Design

## Complete Test Request Payload

```python
class TestExecutionRequest(BaseModel):
    # Test Subject Configuration
    test_subject_model_id: int  # Which AI model to test
    test_prompts: str          # Prompt(s) to send to test subject
    
    # Evaluator Configuration  
    evaluators: List[str]      # Which evaluators to run
    evaluator_model_id: int    # AI model to power the evaluators
    
    # Test Parameters
    test_subject_params: Optional[Dict[str, Any]] = {}  # Override model defaults
    evaluator_params: Optional[Dict[str, Any]] = {}     # Override evaluator model defaults
    
    # Test Execution Settings
    iterations: int = 1
    concurrent_evaluators: bool = True
    save_intermediate_results: bool = True
```

## Complete Data Flow

### Frontend Flow:
1. **System Selection**: User selects AI system to test
2. **Test Subject Model Selection**: 
   - If system has multiple models → user selects which one
   - Currently: system.model_config_id (single model)
3. **Evaluator Selection**: User selects which evaluators to run
4. **Evaluator Model Selection**: User selects AI model to power evaluators
5. **Test Configuration**: User provides prompts and parameters
6. **Send Test Request**: Complete payload sent to backend

### Backend Execution Flow:

```python
async def execute_compliance_test(request: TestExecutionRequest):
    # 1. RESOLVE CONFIGURATIONS
    test_subject_config = await resolve_model_config(request.test_subject_model_id)
    evaluator_model_config = await resolve_model_config(request.evaluator_model_id)
    
    # 2. VALIDATE CONFIGURATIONS  
    validate_api_credentials(test_subject_config)
    validate_api_credentials(evaluator_model_config)
    
    # 3. CALL TEST SUBJECT MODEL via Unified API
    unified_api = get_unified_api()
    test_subject_response = await unified_api.generate(
        config=test_subject_config,
        request=ModelRequest(
            prompt=request.test_prompts,
            **request.test_subject_params
        )
    )
    
    # 4. RUN EVALUATORS
    results = {}
    for evaluator_name in request.evaluators:
        evaluator = get_evaluator(evaluator_name)
        
        # Pass test subject response to evaluator with evaluator AI model config
        evaluation_result = await evaluator.evaluate(
            text=test_subject_response.content,
            test_subject_config=test_subject_config,  # For context
            evaluator_llm_config=evaluator_model_config,  # For LLM-as-judge
            **request.evaluator_params
        )
        
        results[evaluator_name] = evaluation_result
    
    return TestExecutionResult(
        test_id=generate_test_id(),
        test_subject_response=test_subject_response,
        evaluator_results=results,
        metadata={...}
    )
```

## Key Integration Points:

### 1. Unified API Integration
- All AI model calls go through unified API
- Support for multiple providers (OpenAI, Anthropic, Google, etc.)
- Automatic credential management and retry logic

### 2. Evaluator Enhancement
- Evaluators receive both test subject response AND evaluator AI model config
- Rule-based analysis + LLM-as-judge pattern
- Structured JSON output for consistent frontend display

### 3. Security & Credentials
- API keys stored securely in AIModelConfig
- No API keys in test request payload
- Backend resolves credentials from database

### 4. Frontend Display
- Real-time test status updates
- Test subject response display
- Individual evaluator results with scores/violations
- Export capabilities for compliance reports

## Database Schema Enhancements

```sql
-- Support multiple models per system (future enhancement)
CREATE TABLE system_models (
    id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id),
    model_config_id INTEGER REFERENCES ai_model_configs(config_id),
    model_role VARCHAR(50), -- 'primary', 'fallback', 'specialized'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Store test execution results
CREATE TABLE test_executions (
    execution_id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id),
    test_subject_model_id INTEGER REFERENCES ai_model_configs(config_id),
    evaluator_model_id INTEGER REFERENCES ai_model_configs(config_id),
    test_prompts TEXT,
    test_subject_response TEXT,
    evaluator_results JSON,
    status VARCHAR(20) DEFAULT 'running',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```
import { useState, useEffect } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { Search, Filter, Download, Eye, Clock } from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import LoadingSpinner from '../../components/ui/LoadingSpinner';

const StatusBadge = ({ status, score }) => {
  const getStatusInfo = (status) => {
    if (status === 'passed') return { class: 'status-success', text: 'Passed' };
    if (status === 'failed') return { class: 'status-error', text: 'Failed' };
    if (status === 'warning') return { class: 'status-warning', text: 'Warning' };
    return { class: 'status-info', text: 'Running' };
  };

  const { class: statusClass, text } = getStatusInfo(status, score);

  return (
    <div className="flex items-center space-x-2">
      <span className={statusClass}>{text}</span>
      {score !== undefined && (
        <span className="text-sm text-neutral-600">({score}%)</span>
      )}
    </div>
  );
};

const TestResultCard = ({ result, onView }) => {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-neutral-900">{result.system_name}</h3>
            <StatusBadge status={result.status} score={result.overall_score} />
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-neutral-600">Test Date:</span>
              <p className="font-medium">{new Date(result.created_at).toLocaleDateString()}</p>
            </div>
            <div>
              <span className="text-neutral-600">Evaluators:</span>
              <p className="font-medium">{result.evaluators_count}</p>
            </div>
            <div>
              <span className="text-neutral-600">Duration:</span>
              <p className="font-medium">{result.duration}min</p>
            </div>
            <div>
              <span className="text-neutral-600">Issues Found:</span>
              <p className="font-medium text-red-600">{result.issues_count}</p>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {result.evaluator_results?.map((evaluator, index) => (
                <div key={index} className="text-xs">
                  <span className="text-neutral-600">{evaluator.name}:</span>
                  <span className={`ml-1 font-medium ${
                    evaluator.score >= 80 ? 'text-green-600' : 
                    evaluator.score >= 60 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {evaluator.score}%
                  </span>
                </div>
              ))}
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onView(result)}
              >
                <Eye className="w-4 h-4 mr-1" />
                View
              </Button>
              <Button
                variant="outline"
                size="sm"
              >
                <Download className="w-4 h-4 mr-1" />
                Export
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

const TestResultsPage = () => {
  const { testId } = useParams();
  const location = useLocation();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [specificTest, setSpecificTest] = useState(null);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        // If testId is provided, check for results from navigation state or session storage
        if (testId) {
          // First check if result was passed in navigation state (synchronous execution)
          if (location.state?.result) {
            const backendResult = location.state.result;
            
            // Transform backend response to frontend expected format
            const transformedResult = {
              test_subject_prompt: backendResult.test_prompts,
              test_subject_response: backendResult.test_subject_response,
              compliance_score: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.compliance_score,
              compliance_status: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.compliance_status,
              violations: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.violations,
              violations_count: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.violations_count,
              explanation: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.explanation,
              method: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.method,
              llm_model: backendResult.evaluator_model?.model_id,
              llm_provider: backendResult.evaluator_model?.provider,
              processing_time: backendResult.evaluator_results?.[Object.keys(backendResult.evaluator_results)[0]]?.result?.processing_time
            };
            
            setSpecificTest({
              testId: testId,
              status: backendResult.status,
              message: 'Test completed.',
              startTime: new Date().toISOString(),
              completedAt: backendResult.completed_at,
              details: { result: transformedResult }
            });
            setLoading(false);
            return;
          }
          
          // Check session storage
          const storedResult = sessionStorage.getItem(`test_result_${testId}`);
          if (storedResult) {
            const parsedResult = JSON.parse(storedResult);
            
            // Transform if it's the new backend format
            if (parsedResult.evaluator_results) {
              const transformedResult = {
                test_subject_prompt: parsedResult.test_prompts,
                test_subject_response: parsedResult.test_subject_response,
                compliance_score: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.compliance_score,
                compliance_status: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.compliance_status,
                violations: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.violations,
                violations_count: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.violations_count,
                explanation: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.explanation,
                method: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.method,
                llm_model: parsedResult.evaluator_model?.model_id,
                llm_provider: parsedResult.evaluator_model?.provider,
                processing_time: parsedResult.evaluator_results?.[Object.keys(parsedResult.evaluator_results)[0]]?.result?.processing_time
              };
              
              setSpecificTest({
                testId: testId,
                status: parsedResult.status,
                message: 'Test completed.',
                startTime: parsedResult.started_at || new Date().toISOString(),
                completedAt: parsedResult.completed_at,
                details: { result: transformedResult }
              });
            } else {
              // Old format, use as-is
              setSpecificTest({
                testId: testId,
                status: 'completed',
                message: 'Test completed.',
                startTime: parsedResult.started_at || new Date().toISOString(),
                completedAt: new Date().toISOString(),
                details: parsedResult
              });
            }
            setLoading(false);
            return;
          }
          
          // No result found - show error state
          setSpecificTest({
            testId: testId,
            status: 'failed',
            message: 'Test result not found. Please run the test again.',
            startTime: new Date().toISOString()
          });
          setLoading(false);
        }
        
        // Initialize with empty array - results will be populated from API
        setResults([]);
      } catch (error) {
        console.error('Failed to fetch test results:', error);
        setResults([]);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [testId, location.state]);

  const filteredResults = results.filter(result => {
    const matchesSearch = result.system_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || result.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const handleViewResult = (result) => {
    // Navigate to detailed result view
    console.log('View result:', result);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // If viewing a specific test, show the test status
  if (specificTest) {
    // Show completed test results
    if (specificTest.status === 'completed' && specificTest.details) {
      const result = specificTest.details.result;
      return (
        <div className="space-y-6">
          <div className="page-header">
            <h1 className="text-2xl font-bold text-neutral-900">Test Results</h1>
            <p className="text-neutral-600">Test ID: {specificTest.testId}</p>
          </div>
          
          {/* Compliance Score Card */}
          <Card>
            <Card.Content className="p-6">
              <div className="text-center space-y-4">
                <div className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto ${
                  result?.compliance_score >= 80 ? 'bg-green-100' : 
                  result?.compliance_score >= 60 ? 'bg-yellow-100' : 'bg-red-100'
                }`}>
                  <span className={`text-2xl font-bold ${
                    result?.compliance_score >= 80 ? 'text-green-600' : 
                    result?.compliance_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {result?.compliance_score || 'N/A'}
                  </span>
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-neutral-900 mb-2">
                    {result?.compliance_status || 'Test Completed'}
                  </h2>
                  <p className="text-neutral-600">
                    Compliance Score: {result?.compliance_score || 'N/A'}%
                  </p>
                </div>
              </div>
            </Card.Content>
          </Card>

          {/* Test Execution Flow */}
          {result?.test_subject_prompt && (
            <Card>
              <Card.Content className="p-6">
                <h3 className="text-lg font-semibold mb-4">Test Execution Flow</h3>
                <div className="space-y-4">
                  <div>
                    <span className="text-neutral-600 font-medium">1. Original Prompt:</span>
                    <div className="mt-2 p-3 bg-blue-50 border-l-4 border-blue-400 rounded">
                      <p className="text-blue-800">{result.test_subject_prompt}</p>
                    </div>
                  </div>
                  {result?.test_subject_response && (
                    <div>
                      <span className="text-neutral-600 font-medium">2. Test Subject Response:</span>
                      <div className="mt-2 p-3 bg-green-50 border-l-4 border-green-400 rounded">
                        <p className="text-green-800">{result.test_subject_response}</p>
                      </div>
                    </div>
                  )}
                  <div>
                    <span className="text-neutral-600 font-medium">3. Compliance Analysis:</span>
                    <div className="mt-2 p-3 bg-purple-50 border-l-4 border-purple-400 rounded">
                      <p className="text-purple-800">The test subject's response was analyzed for compliance violations</p>
                    </div>
                  </div>
                </div>
              </Card.Content>
            </Card>
          )}

          {/* Test Details */}
          <Card>
            <Card.Content className="p-6">
              <h3 className="text-lg font-semibold mb-4">Test Details</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-neutral-600">Method:</span>
                  <p className="font-medium">{result?.method || 'N/A'}</p>
                </div>
                <div>
                  <span className="text-neutral-600">LLM Model:</span>
                  <p className="font-medium">{result?.llm_model || 'N/A'}</p>
                </div>
                <div>
                  <span className="text-neutral-600">Provider:</span>
                  <p className="font-medium">{result?.llm_provider || 'N/A'}</p>
                </div>
                <div>
                  <span className="text-neutral-600">Processing Time:</span>
                  <p className="font-medium">{result?.processing_time ? `${result.processing_time.toFixed(2)}s` : 'N/A'}</p>
                </div>
              </div>
            </Card.Content>
          </Card>

          {/* Violations */}
          {result?.violations && result.violations.length > 0 && (
            <Card>
              <Card.Content className="p-6">
                <h3 className="text-lg font-semibold mb-4">Violations Found ({result.violations_count || result.violations.length})</h3>
                <div className="space-y-3">
                  {result.violations.map((violation, index) => (
                    <div key={index} className="border-l-4 border-red-400 pl-4 py-2 bg-red-50">
                      <p className="font-medium text-red-800">{violation.framework || 'Compliance Issue'}</p>
                      <p className="text-red-600 text-sm">{violation.issue || violation.description || JSON.stringify(violation)}</p>
                    </div>
                  ))}
                </div>
              </Card.Content>
            </Card>
          )}

          {/* Explanation */}
          {result?.explanation && (
            <Card>
              <Card.Content className="p-6">
                <h3 className="text-lg font-semibold mb-4">Analysis Summary</h3>
                <p className="text-neutral-700 whitespace-pre-wrap">{result.explanation}</p>
              </Card.Content>
            </Card>
          )}

          {/* Raw Response (for debugging) */}
          {result?.raw_response_preview && (
            <Card>
              <Card.Content className="p-6">
                <h3 className="text-lg font-semibold mb-4">Technical Details</h3>
                <pre className="bg-neutral-100 p-4 rounded text-sm overflow-x-auto">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </Card.Content>
            </Card>
          )}
        </div>
      );
    }

    // Show running test
    return (
      <div className="space-y-6">
        <div className="page-header">
          <h1 className="text-2xl font-bold text-neutral-900">Test Results</h1>
          <p className="text-neutral-600">Test ID: {specificTest.testId}</p>
        </div>
        
        <Card>
          <Card.Content className="p-8">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                <Clock className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-neutral-900 mb-2">Test Running</h2>
                <p className="text-neutral-600 max-w-md mx-auto">
                  {specificTest.message}
                </p>
              </div>
              <div className="bg-neutral-50 rounded-lg p-4 inline-block">
                <p className="text-sm text-neutral-600">
                  Started: {new Date(specificTest.startTime).toLocaleString()}
                </p>
              </div>
            </div>
          </Card.Content>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="text-2xl font-bold text-neutral-900">Test Results</h1>
        <p className="text-neutral-600">
          View and analyze your AI system compliance test results
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-neutral-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search test results..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-10"
            />
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-neutral-400" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Results</option>
            <option value="passed">Passed</option>
            <option value="warning">Warning</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
        </div>
        <Button variant="outline">
          <Download className="w-4 h-4 mr-2" />
          Export All
        </Button>
      </div>

      {/* Results List */}
      {filteredResults.length === 0 ? (
        <Card className="text-center py-12">
          <div className="text-neutral-400 mb-4">
            <Eye className="w-12 h-12 mx-auto" />
          </div>
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No test results found</h3>
          <p className="text-neutral-600">
            {searchTerm || filterStatus !== 'all' 
              ? 'Try adjusting your search or filter criteria.'
              : 'Run your first compliance test to see results here.'
            }
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredResults.map((result) => (
            <TestResultCard
              key={result.id}
              result={result}
              onView={handleViewResult}
            />
          ))}
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-2xl font-bold text-neutral-900">{results.length}</div>
          <div className="text-sm text-neutral-600">Total Tests</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-600">
            {results.filter(r => r.status === 'passed').length}
          </div>
          <div className="text-sm text-neutral-600">Passed</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-yellow-600">
            {results.filter(r => r.status === 'warning').length}
          </div>
          <div className="text-sm text-neutral-600">Warnings</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-red-600">
            {results.filter(r => r.status === 'failed').length}
          </div>
          <div className="text-sm text-neutral-600">Failed</div>
        </Card>
      </div>
    </div>
  );
};

export default TestResultsPage;
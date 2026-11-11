import React, { useState, useCallback } from 'react';
import { 
  Upload, 
  FileText, 
  Search, 
  Play, 
  Download, 
  Trash2, 
  Eye,
  AlertCircle,
  CheckCircle,
  Clock
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import LoadingSpinner from '../../components/ui/LoadingSpinner';

const FileUploadZone = ({ onFilesUploaded, uploading }) => {
  const onDrop = useCallback((acceptedFiles) => {
    onFilesUploaded(acceptedFiles);
  }, [onFilesUploaded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
    },
    multiple: true
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
        isDragActive 
          ? 'border-brand-500 bg-brand-50' 
          : 'border-neutral-300 hover:border-neutral-400'
      }`}
    >
      <input {...getInputProps()} />
      <Upload className="w-12 h-12 mx-auto text-neutral-400 mb-4" />
      {uploading ? (
        <div className="space-y-2">
          <LoadingSpinner />
          <p className="text-sm text-neutral-600">Uploading and processing documents...</p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-lg font-medium text-neutral-900">
            {isDragActive ? 'Drop files here' : 'Upload Knowledge Base Documents'}
          </p>
          <p className="text-sm text-neutral-600">
            Drag and drop PDF, TXT, DOC, or DOCX files here, or click to browse
          </p>
          <p className="text-xs text-neutral-500">
            Maximum file size: 10MB per file
          </p>
        </div>
      )}
    </div>
  );
};

const DocumentCard = ({ document, onDelete, onView }) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'processed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'processing':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <FileText className="w-4 h-4 text-neutral-500" />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'processed':
        return 'Ready';
      case 'processing':
        return 'Processing';
      case 'error':
        return 'Error';
      default:
        return 'Pending';
    }
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3 flex-1">
          <FileText className="w-8 h-8 text-brand-600" />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-medium text-neutral-900 truncate">
              {document.name}
            </h4>
            <div className="flex items-center space-x-4 mt-1">
              <span className="text-xs text-neutral-500">
                {document.size} • {document.pages} pages
              </span>
              <div className="flex items-center space-x-1">
                {getStatusIcon(document.status)}
                <span className="text-xs text-neutral-600">
                  {getStatusText(document.status)}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onView(document)}
            disabled={document.status !== 'processed'}
          >
            <Eye className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(document.id)}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
};

const QueryInterface = ({ documents, onRunQuery, queryResult, loading }) => {
  const [query, setQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState('gpt-4');
  const [retrievalSettings, setRetrievalSettings] = useState({
    topK: 5,
    similarity: 0.7,
    maxTokens: 1000
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onRunQuery({
        query: query.trim(),
        model: selectedModel,
        settings: retrievalSettings
      });
    }
  };

  return (
    <Card>
      <Card.Header>
        <Card.Title>RAG Query Interface</Card.Title>
      </Card.Header>
      <Card.Content className="space-y-4">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">
              Query
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your question about the uploaded documents..."
              rows={3}
              className="input"
              disabled={documents.length === 0}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Model
              </label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="input"
              >
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                <option value="claude-3">Claude 3</option>
                <option value="llama-2">Llama 2</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Top K Results
              </label>
              <input
                type="number"
                value={retrievalSettings.topK}
                onChange={(e) => setRetrievalSettings(prev => ({
                  ...prev,
                  topK: parseInt(e.target.value)
                }))}
                min="1"
                max="20"
                className="input"
              />
            </div>
          </div>

          <Button
            type="submit"
            loading={loading}
            disabled={!query.trim() || documents.length === 0 || loading}
            className="w-full"
          >
            <Search className="w-4 h-4 mr-2" />
            Run RAG Query
          </Button>
        </form>

        {queryResult && (
          <div className="mt-6 space-y-4">
            <h4 className="font-medium text-neutral-900">Query Result</h4>
            
            <div className="bg-neutral-50 p-4 rounded-lg">
              <h5 className="text-sm font-medium text-neutral-700 mb-2">Answer</h5>
              <p className="text-sm text-neutral-900 whitespace-pre-wrap">
                {queryResult.answer}
              </p>
            </div>

            <div className="space-y-2">
              <h5 className="text-sm font-medium text-neutral-700">Retrieved Context</h5>
              {queryResult.context.map((ctx, index) => (
                <div key={index} className="bg-white border border-neutral-200 p-3 rounded">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-neutral-600">
                      {ctx.source} (Page {ctx.page})
                    </span>
                    <span className="text-xs text-neutral-500">
                      Similarity: {(ctx.similarity * 100).toFixed(1)}%
                    </span>
                  </div>
                  <p className="text-sm text-neutral-800">{ctx.text}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <p className="text-lg font-semibold text-neutral-900">
                  {queryResult.metrics.responseTime}ms
                </p>
                <p className="text-xs text-neutral-600">Response Time</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-neutral-900">
                  {queryResult.metrics.tokensUsed}
                </p>
                <p className="text-xs text-neutral-600">Tokens Used</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-neutral-900">
                  {queryResult.metrics.documentsSearched}
                </p>
                <p className="text-xs text-neutral-600">Docs Searched</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-neutral-900">
                  {(queryResult.metrics.avgSimilarity * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-neutral-600">Avg Similarity</p>
              </div>
            </div>
          </div>
        )}
      </Card.Content>
    </Card>
  );
};

const RAGTestPage = () => {
  const [documents, setDocuments] = useState([
    {
      id: 1,
      name: 'GDPR_Compliance_Guide.pdf',
      size: '2.4 MB',
      pages: 45,
      status: 'processed',
      uploadedAt: '2024-01-15T10:30:00Z'
    },
    {
      id: 2,
      name: 'AI_Ethics_Framework.pdf',
      size: '1.8 MB',
      pages: 32,
      status: 'processed',
      uploadedAt: '2024-01-14T14:20:00Z'
    },
    {
      id: 3,
      name: 'Model_Documentation.docx',
      size: '856 KB',
      pages: 12,
      status: 'processing',
      uploadedAt: '2024-01-16T09:15:00Z'
    }
  ]);
  const [uploading, setUploading] = useState(false);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryResult, setQueryResult] = useState(null);

  const handleFilesUploaded = async (files) => {
    setUploading(true);
    try {
      // Simulate file upload and processing
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const newDocuments = files.map((file, index) => ({
        id: documents.length + index + 1,
        name: file.name,
        size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
        pages: Math.floor(Math.random() * 50) + 10,
        status: 'processing',
        uploadedAt: new Date().toISOString()
      }));

      setDocuments(prev => [...prev, ...newDocuments]);

      // Simulate processing completion
      setTimeout(() => {
        setDocuments(prev => prev.map(doc => 
          newDocuments.find(newDoc => newDoc.id === doc.id)
            ? { ...doc, status: 'processed' }
            : doc
        ));
      }, 3000);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = (id) => {
    setDocuments(prev => prev.filter(doc => doc.id !== id));
  };

  const handleViewDocument = (document) => {
    console.log('View document:', document);
    // In a real app, this would open a document viewer
  };

  const handleRunQuery = async (queryData) => {
    setQueryLoading(true);
    try {
      // Call RAG service API
      const response = await api.post('/compliance/rag/query', queryData);
      setQueryResult(response.data);
    } catch (error) {
      console.error('Query failed:', error);
      setQueryResult({ error: 'Query failed: ' + error.message });
    } finally {
      setQueryLoading(false);
    }
  };

  const processedDocs = documents.filter(d => d.status === 'processed').length;
  const processingDocs = documents.filter(d => d.status === 'processing').length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="text-2xl font-bold text-neutral-900">RAG Testing</h1>
        <p className="text-neutral-600">
          Upload documents and test Retrieval-Augmented Generation capabilities
        </p>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-2xl font-bold text-neutral-900">{documents.length}</div>
          <div className="text-sm text-neutral-600">Total Documents</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-600">{processedDocs}</div>
          <div className="text-sm text-neutral-600">Ready for Query</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-yellow-600">{processingDocs}</div>
          <div className="text-sm text-neutral-600">Processing</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-blue-600">
            {documents.reduce((sum, doc) => sum + parseInt(doc.pages), 0)}
          </div>
          <div className="text-sm text-neutral-600">Total Pages</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Management */}
        <div className="space-y-6">
          <Card>
            <Card.Header>
              <Card.Title>Knowledge Base Documents</Card.Title>
            </Card.Header>
            <Card.Content>
              <FileUploadZone 
                onFilesUploaded={handleFilesUploaded}
                uploading={uploading}
              />
            </Card.Content>
          </Card>

          <Card>
            <Card.Header>
              <div className="flex items-center justify-between">
                <Card.Title>Uploaded Documents</Card.Title>
                <Button variant="outline" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  Export List
                </Button>
              </div>
            </Card.Header>
            <Card.Content>
              <div className="space-y-3">
                {documents.length === 0 ? (
                  <div className="text-center py-8 text-neutral-500">
                    <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No documents uploaded yet</p>
                  </div>
                ) : (
                  documents.map((document) => (
                    <DocumentCard
                      key={document.id}
                      document={document}
                      onDelete={handleDeleteDocument}
                      onView={handleViewDocument}
                    />
                  ))
                )}
              </div>
            </Card.Content>
          </Card>
        </div>

        {/* Query Interface */}
        <div>
          <QueryInterface
            documents={documents.filter(d => d.status === 'processed')}
            onRunQuery={handleRunQuery}
            queryResult={queryResult}
            loading={queryLoading}
          />
        </div>
      </div>
    </div>
  );
};

export default RAGTestPage;
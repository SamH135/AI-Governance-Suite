import { useState } from 'react';
import { Play, Save, Copy, Zap, Code, FileText } from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

const PromptEngineeringPage = () => {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState({
    model: 'gpt-4',
    temperature: 0.7,
    maxTokens: 1000,
    topP: 1.0
  });

  const handleRunPrompt = async () => {
    setLoading(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      setResponse('This is a simulated response from the AI model. In a real implementation, this would be the actual response from your selected model.');
    } catch (error) {
      console.error('Failed to run prompt:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSavePrompt = () => {
    // Save prompt logic
    console.log('Saving prompt:', prompt);
  };

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(prompt);
  };

  const templates = [
    {
      name: 'Classification',
      description: 'Classify text into categories',
      template: 'Classify the following text into one of these categories: [categories]\n\nText: {text}\n\nCategory:'
    },
    {
      name: 'Summarization',
      description: 'Summarize long text',
      template: 'Please provide a concise summary of the following text:\n\n{text}\n\nSummary:'
    },
    {
      name: 'Question Answering',
      description: 'Answer questions based on context',
      template: 'Based on the following context, answer the question:\n\nContext: {context}\n\nQuestion: {question}\n\nAnswer:'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="text-2xl font-bold text-neutral-900">Prompt Engineering Lab</h1>
        <p className="text-neutral-600">
          Create, test, and optimize AI prompts with real-time feedback
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Editor */}
        <div className="lg:col-span-3 space-y-6">
          {/* Prompt Editor */}
          <Card>
            <Card.Header>
              <div className="flex items-center justify-between">
                <Card.Title>Prompt Editor</Card.Title>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyPrompt}
                  >
                    <Copy className="w-4 h-4 mr-1" />
                    Copy
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSavePrompt}
                  >
                    <Save className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={handleRunPrompt}
                    loading={loading}
                    disabled={!prompt.trim()}
                  >
                    <Play className="w-4 h-4 mr-1" />
                    Run
                  </Button>
                </div>
              </div>
            </Card.Header>
            <Card.Content>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter your prompt here..."
                rows={12}
                className="input resize-none font-mono text-sm"
              />
            </Card.Content>
          </Card>

          {/* Response */}
          <Card>
            <Card.Header>
              <Card.Title>Model Response</Card.Title>
            </Card.Header>
            <Card.Content>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
                  <span className="ml-2 text-neutral-600">Generating response...</span>
                </div>
              ) : response ? (
                <div className="bg-neutral-50 p-4 rounded-lg">
                  <pre className="whitespace-pre-wrap text-sm text-neutral-900">{response}</pre>
                </div>
              ) : (
                <div className="text-center py-8 text-neutral-500">
                  <Zap className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>Run a prompt to see the response here</p>
                </div>
              )}
            </Card.Content>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Model Settings */}
          <Card>
            <Card.Header>
              <Card.Title>Model Settings</Card.Title>
            </Card.Header>
            <Card.Content className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Model
                </label>
                <select
                  value={settings.model}
                  onChange={(e) => setSettings(prev => ({ ...prev, model: e.target.value }))}
                  className="input"
                >
                  <option value="gpt-4">GPT-4</option>
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  <option value="claude-3">Claude 3</option>
                  <option value="llama-2">Llama 2</option>
                </select>
              </div>

              <Input
                label="Temperature"
                type="number"
                value={settings.temperature}
                onChange={(e) => setSettings(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                min="0"
                max="2"
                step="0.1"
              />

              <Input
                label="Max Tokens"
                type="number"
                value={settings.maxTokens}
                onChange={(e) => setSettings(prev => ({ ...prev, maxTokens: parseInt(e.target.value) }))}
                min="1"
                max="4000"
              />

              <Input
                label="Top P"
                type="number"
                value={settings.topP}
                onChange={(e) => setSettings(prev => ({ ...prev, topP: parseFloat(e.target.value) }))}
                min="0"
                max="1"
                step="0.1"
              />
            </Card.Content>
          </Card>

          {/* Prompt Templates */}
          <Card>
            <Card.Header>
              <Card.Title>Prompt Templates</Card.Title>
            </Card.Header>
            <Card.Content>
              <div className="space-y-3">
                {templates.map((template, index) => (
                  <div
                    key={index}
                    className="p-3 border border-neutral-200 rounded-lg cursor-pointer hover:bg-neutral-50 transition-colors"
                    onClick={() => setPrompt(template.template)}
                  >
                    <div className="flex items-center mb-1">
                      <Code className="w-4 h-4 mr-2 text-brand-600" />
                      <h4 className="text-sm font-medium text-neutral-900">{template.name}</h4>
                    </div>
                    <p className="text-xs text-neutral-600">{template.description}</p>
                  </div>
                ))}
              </div>
            </Card.Content>
          </Card>

          {/* Quick Actions */}
          <Card>
            <Card.Header>
              <Card.Title>Quick Actions</Card.Title>
            </Card.Header>
            <Card.Content className="space-y-2">
              <Button variant="outline" size="sm" className="w-full justify-start">
                <FileText className="w-4 h-4 mr-2" />
                View History
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start">
                <Save className="w-4 h-4 mr-2" />
                Save as Template
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start">
                <Zap className="w-4 h-4 mr-2" />
                Optimize Prompt
              </Button>
            </Card.Content>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PromptEngineeringPage;
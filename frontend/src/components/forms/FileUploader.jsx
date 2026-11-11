import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X } from 'lucide-react';
import Button from '../ui/Button';

const FileUploader = ({ 
  onFilesUploaded, 
  acceptedTypes = {}, 
  maxFiles = 10,
  maxSize = 10 * 1024 * 1024, // 10MB
  multiple = true,
  uploading = false,
  uploadedFiles = [],
  onRemoveFile
}) => {
  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    if (rejectedFiles.length > 0) {
      console.warn('Some files were rejected:', rejectedFiles);
    }
    if (acceptedFiles.length > 0) {
      onFilesUploaded(acceptedFiles);
    }
  }, [onFilesUploaded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedTypes,
    multiple,
    maxFiles,
    maxSize
  });

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive 
            ? 'border-brand-500 bg-brand-50' 
            : 'border-neutral-300 hover:border-neutral-400'
        } ${uploading ? 'pointer-events-none opacity-50' : ''}`}
      >
        <input {...getInputProps()} />
        <Upload className="w-12 h-12 mx-auto text-neutral-400 mb-4" />
        {uploading ? (
          <div className="space-y-2">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600 mx-auto"></div>
            <p className="text-sm text-neutral-600">Uploading files...</p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-lg font-medium text-neutral-900">
              {isDragActive ? 'Drop files here' : 'Upload Files'}
            </p>
            <p className="text-sm text-neutral-600">
              Drag and drop files here, or click to browse
            </p>
            <p className="text-xs text-neutral-500">
              Max {maxFiles} files, {formatFileSize(maxSize)} per file
            </p>
          </div>
        )}
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-neutral-900">Uploaded Files</h4>
          <div className="space-y-2">
            {uploadedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-neutral-50 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <File className="w-5 h-5 text-neutral-400" />
                  <div>
                    <p className="text-sm font-medium text-neutral-900">{file.name}</p>
                    <p className="text-xs text-neutral-500">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                {onRemoveFile && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemoveFile(index)}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUploader;
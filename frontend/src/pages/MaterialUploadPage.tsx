import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  Download,
  Eye,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Wand2,
  Cpu
} from 'lucide-react';
import { previewSampleMaterials, previewCsvUpload, normalizeText, extractAttributes } from '../services/api';
import { CSVPreviewResponseData, TextNormalizationResult, AttributeExtractionResult } from '../types';

export const MaterialUploadPage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedPsu, setSelectedPsu] = useState('Indian Railways (Northern)');
  const [selectedSystem] = useState('SAP_ECC_PRD');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<CSVPreviewResponseData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Advanced Tools Accordion State (Collapsed by default)
  const [showAdvancedTools, setShowAdvancedTools] = useState<boolean>(false);

  // Normalization tester state
  const [normInputDesc, setNormInputDesc] = useState('SS PIPE 50 NB SCH 40 ASTM A312');
  const normInputUom = 'MTR';
  const normInputCat = 'piping';
  const [isNormLoading, setIsNormLoading] = useState(false);
  const [normResult, setNormResult] = useState<TextNormalizationResult | null>(null);

  // Attribute extraction tester state
  const [extractInputDesc, setExtractInputDesc] = useState('BEARING 6205 ZZ');
  const [isExtractLoading, setIsExtractLoading] = useState(false);
  const [extractResult, setExtractResult] = useState<AttributeExtractionResult | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Automatically load sample data on initial mount if not yet loaded
  useEffect(() => {
    handlePreviewSample();
  }, []);

  const handlePreviewSample = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await previewSampleMaterials();
      setPreviewData(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load sample data.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadPreview = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select a CSV file first.');
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await previewCsvUpload(selectedFile, selectedPsu, selectedSystem);
      setPreviewData(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to parse CSV upload.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  const handleRunNormalization = async (desc?: string, uom?: string, cat?: string) => {
    const raw = desc !== undefined ? desc : normInputDesc;
    const u = uom !== undefined ? uom : normInputUom;
    const c = cat !== undefined ? cat : normInputCat;
    if (!raw.trim()) return;

    setIsNormLoading(true);
    try {
      const res = await normalizeText({
        raw_description: raw,
        uom: u || undefined,
        category: c || undefined
      });
      setNormResult(res);
    } catch {
      // Graceful error
    } finally {
      setIsNormLoading(false);
    }
  };

  const handleRunExtraction = async (desc?: string) => {
    const raw = desc !== undefined ? desc : extractInputDesc;
    if (!raw.trim()) return;

    setIsExtractLoading(true);
    try {
      const res = await extractAttributes({ raw_description: raw });
      setExtractResult(res);
    } catch {
      // Graceful error
    } finally {
      setIsExtractLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Upload Materials</h2>
          <p className="text-xs text-gray-600 mt-1">
            Upload CSV spreadsheets from CPSEs or inspect sample data. The system cleans descriptions and standardizes units automatically.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handlePreviewSample}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50"
          >
            {isLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />}
            <span>Preview Sample Data</span>
          </button>
          <a
            href="/sample-data/sample_materials_raw.csv"
            download
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-gray-500" />
            <span>Download Sample CSV</span>
          </a>
        </div>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="p-4 rounded-md border border-red-200 bg-red-50 text-red-700 text-xs flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="text-red-700 font-bold underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Upload Dropzone & Quick Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Source Settings */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">
            Source Organization
          </h3>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Select PSU / Enterprise
            </label>
            <select
              value={selectedPsu}
              onChange={(e) => setSelectedPsu(e.target.value)}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-xs text-gray-900 focus:outline-none focus:border-blue-500"
            >
              <option value="Indian Railways (Northern)">Indian Railways (Northern)</option>
              <option value="Coal India Limited">Coal India Limited (CIL)</option>
              <option value="Steel Authority of India Ltd">Steel Authority of India (SAIL)</option>
              <option value="Oil and Natural Gas Corp">Oil and Natural Gas Corp (ONGC)</option>
              <option value="NTPC Limited">NTPC Limited</option>
              <option value="Bharat Heavy Electricals">Bharat Heavy Electricals (BHEL)</option>
              <option value="Indian Oil Corporation">Indian Oil Corporation (IOCL)</option>
            </select>
          </div>

          <div className="p-3 bg-blue-50 rounded-md border border-blue-100 text-xs text-blue-800 space-y-1">
            <p className="font-semibold">Automatic Processing:</p>
            <p className="text-blue-700 leading-relaxed text-[11px]">
              - Strips special characters and redundant spaces.<br />
              - Converts units (e.g. MTR &rarr; M, NOS &rarr; EA).<br />
              - Prepares records for duplicate comparison.
            </p>
          </div>
        </div>

        {/* CSV Dropzone */}
        <div className="md:col-span-2 bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col justify-between">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv"
            className="hidden"
          />

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 hover:border-blue-500 rounded-lg p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-gray-50 hover:bg-white"
          >
            <UploadCloud className="w-8 h-8 text-blue-600 mb-2" />
            <h4 className="text-sm font-semibold text-gray-900">
              {selectedFile ? selectedFile.name : 'Click to select CSV spreadsheet or drag & drop'}
            </h4>
            <p className="text-xs text-gray-500 mt-1">
              Supports standard CPSE procurement format with item codes, descriptions, and units.
            </p>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-gray-500">
              {selectedFile ? `Selected: ${selectedFile.name}` : 'Loaded: Sample CPSE Material Catalog'}
            </span>
            <button
              onClick={handleUploadPreview}
              disabled={isLoading || !selectedFile}
              className="px-4 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              Parse Selected File
            </button>
          </div>
        </div>
      </div>

      {/* Main Table: Uploaded Materials */}
      {previewData && (
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
            <div>
              <h3 className="text-sm font-bold text-gray-900">
                Uploaded Materials Table ({previewData.valid_records.length} Records)
              </h3>
              <p className="text-xs text-gray-500">
                Cleaned and standardized records ready for duplicate detection.
              </p>
            </div>
            <span className="px-2.5 py-1 rounded text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
              Valid Catalog
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-100 text-gray-600 font-semibold border-b border-gray-200">
                <tr>
                  <th className="py-2.5 px-4">Item Code</th>
                  <th className="py-2.5 px-4">Original Description</th>
                  <th className="py-2.5 px-4">Standardized Description</th>
                  <th className="py-2.5 px-4">Unit</th>
                  <th className="py-2.5 px-4">Category</th>
                  <th className="py-2.5 px-4">Source Organization</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {previewData.valid_records.map((rec) => (
                  <tr key={rec.id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-2.5 px-4 font-mono font-medium text-blue-700">
                      {rec.source_material_code}
                    </td>
                    <td className="py-2.5 px-4 text-gray-600 max-w-xs">
                      {rec.raw_description}
                    </td>
                    <td className="py-2.5 px-4 text-gray-900 font-medium max-w-xs">
                      {rec.standard_description || rec.raw_description}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-300 font-mono font-bold text-gray-700">
                        {rec.uom}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-gray-600">
                      {rec.category}
                    </td>
                    <td className="py-2.5 px-4 text-gray-700 font-medium">
                      {rec.source_cpse}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Collapsed Advanced Section: Normalization & Attribute Extraction */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
        <button
          type="button"
          onClick={() => setShowAdvancedTools(!showAdvancedTools)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-gray-50 transition-colors rounded-lg"
        >
          <div className="flex items-center gap-2">
            <Wand2 className="w-4 h-4 text-blue-600" />
            <div>
              <h3 className="text-sm font-bold text-gray-900">
                Advanced: Normalization & Attribute Extraction Tools
              </h3>
              <p className="text-xs text-gray-500">
                Test individual description cleaning, UOM standardization, and technical specification extraction.
              </p>
            </div>
          </div>
          <span className="text-xs text-blue-600 font-medium flex items-center gap-1">
            {showAdvancedTools ? 'Hide Tools' : 'Show Tools'}
            {showAdvancedTools ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </span>
        </button>

        {showAdvancedTools && (
          <div className="p-5 border-t border-gray-200 space-y-6 bg-gray-50">
            {/* Tool 1: Normalization Tester */}
            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
              <h4 className="text-xs font-bold uppercase text-gray-700 flex items-center gap-1.5">
                <Wand2 className="w-3.5 h-3.5 text-blue-600" />
                Text Normalization Tester
              </h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={normInputDesc}
                  onChange={(e) => setNormInputDesc(e.target.value)}
                  placeholder="e.g. SS PIPE 50 NB SCH 40"
                  className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => handleRunNormalization()}
                  disabled={isNormLoading}
                  className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {isNormLoading ? 'Cleaning...' : 'Normalize'}
                </button>
              </div>

              {normResult && (
                <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs space-y-1">
                  <p><strong>Standard Description:</strong> <span className="text-blue-700">{normResult.standard_description}</span></p>
                  <p><strong>Cleaned Text:</strong> {normResult.cleaned_description}</p>
                  <p><strong>Normalized UOM:</strong> {normResult.normalized_uom || 'N/A'}</p>
                </div>
              )}
            </div>

            {/* Tool 2: Attribute Extraction Tester */}
            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
              <h4 className="text-xs font-bold uppercase text-gray-700 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-blue-600" />
                Technical Attribute Extraction Tester
              </h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={extractInputDesc}
                  onChange={(e) => setExtractInputDesc(e.target.value)}
                  placeholder="e.g. BEARING 6205 ZZ"
                  className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => handleRunExtraction()}
                  disabled={isExtractLoading}
                  className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {isExtractLoading ? 'Extracting...' : 'Extract'}
                </button>
              </div>

              {extractResult && (
                <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs space-y-2">
                  <p><strong>Category:</strong> {extractResult.inferred_category}</p>
                  <p><strong>Extracted Parameters:</strong></p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(extractResult.extracted_attributes).map(([k, v]) => (
                      <span key={k} className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-mono text-[11px]">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

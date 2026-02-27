import React, { useState, useRef, useCallback, useEffect, type ReactNode } from 'react';
import {
  FolderOpen,
  Folder,
  ChevronRight,
  ChevronDown,
  Plus,
  Trash2,
  Upload,
  Film,
  Image,
  Music,
  Sparkles,
  ImageIcon,
  Pencil,
} from 'lucide-react';
import type { Asset } from '@/react-app/hooks/useProject';

export interface Bin {
  id: string;
  name: string;
  icon: string;
  assets: Asset[];
  children?: Bin[];
}

export interface AssetBinBrowserProps {
  sessionId: string | null;
  bins: Bin[];
  selectedAssetId?: string | null;
  onAssetSelect: (assetId: string | null) => void;
  onBinCreate: (name: string, parentId?: string) => void;
  onAssetMoveToBin: (assetId: string, binId: string) => void;
  assets: Asset[];
  onUpload: (files: FileList) => void;
  onDelete: (assetId: string) => void;
  onDragStart: (asset: Asset) => void;
  uploading?: boolean;
  onOpenGifSearch?: () => void;
  onBinDelete?: (binId: string) => void;
  onBinRename?: (binId: string, name: string) => void;
}

interface ContextMenuState {
  x: number;
  y: number;
  binId: string | null;
}

// Static lookup maps — Tailwind can purge safely since all class strings are literals
const assetIconMap = {
  video: Film,
  image: Image,
  audio: Music,
} as const;

const getAssetIcon = (type: Asset['type']) => assetIconMap[type] ?? Film;

const assetGradientMap: Record<string, string> = {
  video: 'from-blue-500 to-cyan-500',
  image: 'from-amber-500 to-orange-500',
  audio: 'from-emerald-500 to-teal-500',
  default: 'from-gray-500 to-gray-600',
};

const getAssetGradient = (type: Asset['type']): string =>
  assetGradientMap[type] ?? assetGradientMap.default;

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function findBin(bins: Bin[], id: string): Bin | undefined {
  for (const bin of bins) {
    if (bin.id === id) return bin;
    if (bin.children) {
      const found = findBin(bin.children, id);
      if (found) return found;
    }
  }
  return undefined;
}

function collectBinAssets(bin: Bin): Asset[] {
  const result = [...bin.assets];
  if (bin.children) {
    for (const child of bin.children) {
      result.push(...collectBinAssets(child));
    }
  }
  return result;
}

export default function AssetBinBrowser({
  sessionId: _sessionId,
  bins,
  selectedAssetId,
  onAssetSelect,
  onBinCreate,
  onAssetMoveToBin,
  assets,
  onUpload,
  onDelete,
  onDragStart,
  uploading = false,
  onOpenGifSearch,
  onBinDelete,
  onBinRename,
}: AssetBinBrowserProps) {
  const [activeBinId, setActiveBinId] = useState<string>('all');
  const [expandedBins, setExpandedBins] = useState<Set<string>>(new Set());
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [renamingBinId, setRenamingBinId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [dragOverBinId, setDragOverBinId] = useState<string | null>(null);
  const [showNewBinInput, setShowNewBinInput] = useState(false);
  const [newBinName, setNewBinName] = useState('');
  const [newBinParentId, setNewBinParentId] = useState<string | undefined>(undefined);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const newBinInputRef = useRef<HTMLInputElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // Filtered assets for the selected bin
  const filteredAssets = activeBinId === 'all'
    ? assets
    : (() => {
        const bin = findBin(bins, activeBinId);
        return bin ? collectBinAssets(bin) : assets;
      })();

  // Close context menu on outside click
  useEffect(() => {
    if (!contextMenu) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [contextMenu]);

  // Auto-focus new bin input
  useEffect(() => {
    if (showNewBinInput) newBinInputRef.current?.focus();
  }, [showNewBinInput]);

  const handleBinSelect = useCallback((binId: string) => {
    setActiveBinId(binId);
  }, []);

  const handleBinToggle = useCallback((binId: string) => {
    setExpandedBins(prev => {
      const next = new Set(prev);
      if (next.has(binId)) next.delete(binId);
      else next.add(binId);
      return next;
    });
  }, []);

  const handleContextMenu = useCallback((e: React.MouseEvent, binId: string | null) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, binId });
  }, []);

  const handleDragOverBin = useCallback((e: React.DragEvent, binId: string) => {
    if (e.dataTransfer.types.includes('application/x-hyperedit-asset')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      setDragOverBinId(binId);
    }
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverBinId(null);
  }, []);

  const handleDropOnBin = useCallback((e: React.DragEvent, binId: string) => {
    e.preventDefault();
    setDragOverBinId(null);
    const raw = e.dataTransfer.getData('application/x-hyperedit-asset');
    if (raw) {
      try {
        const asset = JSON.parse(raw) as Asset;
        onAssetMoveToBin(asset.id, binId);
      } catch {
        // ignore
      }
    }
  }, [onAssetMoveToBin]);

  const handleRenameStart = useCallback((binId: string, currentName: string) => {
    setRenamingBinId(binId);
    setRenameValue(currentName);
    setContextMenu(null);
  }, []);

  const handleRenameSubmit = useCallback((binId: string) => {
    if (renameValue.trim()) onBinRename?.(binId, renameValue.trim());
    setRenamingBinId(null);
    setRenameValue('');
  }, [renameValue, onBinRename]);

  const handleRenameCancel = useCallback(() => {
    setRenamingBinId(null);
    setRenameValue('');
  }, []);

  const handleNewBinSubmit = useCallback(() => {
    if (newBinName.trim()) onBinCreate(newBinName.trim(), newBinParentId);
    setNewBinName('');
    setShowNewBinInput(false);
    setNewBinParentId(undefined);
  }, [newBinName, newBinParentId, onBinCreate]);

  const handleFileSelect = useCallback(() => fileInputRef.current?.click(), []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      onUpload(files);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [onUpload]);

  const handleGridDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length > 0) onUpload(e.dataTransfer.files);
  }, [onUpload]);

  const handleGridDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes('Files')) e.preventDefault();
  }, []);

  // Recursive bin row renderer
  const renderBinRow = (bin: Bin, depth: number): ReactNode => {
    const hasChildren = !!(bin.children && bin.children.length > 0);
    const isExpanded = expandedBins.has(bin.id);
    const isSelected = activeBinId === bin.id;
    const isDragOver = dragOverBinId === bin.id;
    const isRenaming = renamingBinId === bin.id;
    const totalCount = collectBinAssets(bin).length;

    return (
      <div key={bin.id}>
        <div
          className={`flex items-center gap-1 py-1 cursor-pointer rounded transition-colors select-none
            ${isSelected ? 'bg-orange-500/15 text-orange-400' : 'hover:bg-zinc-800/70 text-zinc-300'}
            ${isDragOver ? 'ring-1 ring-orange-500/40 bg-orange-500/10' : ''}
          `}
          style={{ paddingLeft: `${4 + depth * 12}px`, paddingRight: '8px' }}
          onClick={() => handleBinSelect(bin.id)}
          onDoubleClick={() => handleBinToggle(bin.id)}
          onContextMenu={(e) => handleContextMenu(e, bin.id)}
          onDragOver={(e) => handleDragOverBin(e, bin.id)}
          onDragLeave={handleDragLeave}
          onDrop={(e) => handleDropOnBin(e, bin.id)}
        >
          {/* Expand/collapse chevron */}
          <span
            className="w-3 h-3 flex-shrink-0 text-zinc-500"
            onClick={(e) => {
              e.stopPropagation();
              if (hasChildren) handleBinToggle(bin.id);
            }}
          >
            {hasChildren
              ? (isExpanded
                  ? <ChevronDown className="w-3 h-3" />
                  : <ChevronRight className="w-3 h-3" />)
              : null}
          </span>

          {/* Folder icon */}
          {isSelected || isExpanded
            ? <FolderOpen className="w-3.5 h-3.5 flex-shrink-0 text-orange-400/70" />
            : <Folder className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
          }

          {/* Name or inline rename input */}
          {isRenaming ? (
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameSubmit(bin.id);
                if (e.key === 'Escape') handleRenameCancel();
              }}
              onBlur={() => handleRenameSubmit(bin.id)}
              className="flex-1 min-w-0 bg-zinc-700 text-zinc-100 text-xs px-1 py-0.5 rounded border border-zinc-600 outline-none"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className="flex-1 min-w-0 text-xs truncate">{bin.name}</span>
          )}

          {/* Count badge */}
          {!isRenaming && (
            <span className="text-[10px] text-zinc-500 bg-zinc-800 px-1 py-0.5 rounded-full flex-shrink-0">
              {totalCount}
            </span>
          )}
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div>{bin.children!.map(child => renderBinRow(child, depth + 1))}</div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-zinc-900/50 border-r border-zinc-800/50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/50 flex-shrink-0">
        <span className="text-xs font-medium text-zinc-400">Asset Bins</span>
        <div className="flex items-center gap-1">
          {onOpenGifSearch && (
            <button
              onClick={onOpenGifSearch}
              className="p-1.5 bg-purple-600 hover:bg-purple-500 rounded text-xs transition-colors"
              title="Search GIFs & Memes"
            >
              <ImageIcon className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={() => {
              setNewBinParentId(undefined);
              setShowNewBinInput(true);
              setContextMenu(null);
            }}
            className="p-1.5 bg-zinc-700 hover:bg-zinc-600 rounded text-xs transition-colors"
            title="New bin"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleFileSelect}
            disabled={uploading}
            className="p-1.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-xs transition-colors"
            title="Import files"
          >
            <Upload className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="video/*,image/*,audio/*"
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Bin Tree */}
      <div
        className="flex-shrink-0 max-h-44 overflow-y-auto py-1 border-b border-zinc-800/50"
        onContextMenu={(e) => {
          // Right-click on empty area → context menu with no binId
          if (e.target === e.currentTarget) handleContextMenu(e, null);
        }}
      >
        {/* All Assets virtual bin */}
        <div
          className={`flex items-center gap-1 py-1 cursor-pointer rounded transition-colors select-none
            ${activeBinId === 'all' ? 'bg-orange-500/15 text-orange-400' : 'hover:bg-zinc-800/70 text-zinc-300'}
          `}
          style={{ paddingLeft: '4px', paddingRight: '8px' }}
          onClick={() => setActiveBinId('all')}
          onContextMenu={(e) => handleContextMenu(e, null)}
        >
          <span className="w-3 h-3 flex-shrink-0" />
          <FolderOpen className="w-3.5 h-3.5 flex-shrink-0 text-orange-400/70" />
          <span className="flex-1 min-w-0 text-xs truncate">All Assets</span>
          <span className="text-[10px] text-zinc-500 bg-zinc-800 px-1 py-0.5 rounded-full flex-shrink-0">
            {assets.length}
          </span>
        </div>

        {/* Classification bins */}
        {bins.map(bin => renderBinRow(bin, 0))}

        {/* New bin inline input */}
        {showNewBinInput && (
          <div className="flex items-center gap-1 px-2 py-1">
            <span className="w-3 h-3 flex-shrink-0" />
            <Folder className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
            <input
              ref={newBinInputRef}
              value={newBinName}
              onChange={(e) => setNewBinName(e.target.value)}
              placeholder="Bin name…"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleNewBinSubmit();
                if (e.key === 'Escape') {
                  setShowNewBinInput(false);
                  setNewBinName('');
                }
              }}
              onBlur={handleNewBinSubmit}
              className="flex-1 min-w-0 bg-zinc-700 text-zinc-100 text-xs px-1 py-0.5 rounded border border-zinc-600 outline-none"
            />
          </div>
        )}
      </div>

      {/* Asset Grid */}
      <div
        className="flex-1 overflow-auto p-2 relative"
        onDrop={handleGridDrop}
        onDragOver={handleGridDragOver}
      >
        {filteredAssets.length === 0 ? (
          <div
            onClick={handleFileSelect}
            className="flex flex-col items-center justify-center h-full min-h-20 p-4 border-2 border-dashed border-zinc-700 rounded-lg cursor-pointer hover:border-orange-500/50 hover:bg-orange-500/5 transition-colors"
          >
            <Upload className="w-6 h-6 text-zinc-500 mb-1.5" />
            <span className="text-xs text-zinc-500 text-center">
              {activeBinId === 'all'
                ? 'Drop files or click to upload'
                : 'No assets in this bin'}
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {filteredAssets.map(asset => (
              <BinAssetCard
                key={asset.id}
                asset={asset}
                isSelected={selectedAssetId === asset.id}
                onSelect={() => onAssetSelect(selectedAssetId === asset.id ? null : asset.id)}
                onDelete={() => onDelete(asset.id)}
                onDragStart={() => onDragStart(asset)}
              />
            ))}
            <button
              onClick={handleFileSelect}
              disabled={uploading}
              className="aspect-video flex flex-col items-center justify-center border-2 border-dashed border-zinc-700 rounded-lg cursor-pointer hover:border-orange-500/50 hover:bg-orange-500/5 transition-colors disabled:opacity-50"
            >
              <Plus className="w-5 h-5 text-zinc-500" />
              <span className="text-[10px] text-zinc-500 mt-1">Add</span>
            </button>
          </div>
        )}

        {uploading && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center pointer-events-none">
            <div className="animate-spin w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full" />
          </div>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          ref={contextMenuRef}
          className="fixed z-50 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl py-1 min-w-36 text-xs"
          style={{ top: contextMenu.y, left: contextMenu.x }}
        >
          <button
            className="w-full text-left px-3 py-1.5 hover:bg-zinc-700 text-zinc-200 flex items-center gap-2 transition-colors"
            onClick={() => {
              setNewBinParentId(contextMenu.binId ?? undefined);
              setShowNewBinInput(true);
              setContextMenu(null);
            }}
          >
            <Plus className="w-3.5 h-3.5" />
            {contextMenu.binId ? 'New Sub-bin' : 'New Bin'}
          </button>
          {contextMenu.binId && (
            <>
              <button
                className="w-full text-left px-3 py-1.5 hover:bg-zinc-700 text-zinc-200 flex items-center gap-2 transition-colors"
                onClick={() => {
                  const bin = findBin(bins, contextMenu.binId!);
                  if (bin) handleRenameStart(bin.id, bin.name);
                }}
              >
                <Pencil className="w-3.5 h-3.5" />
                Rename
              </button>
              <div className="my-1 border-t border-zinc-700" />
              <button
                className="w-full text-left px-3 py-1.5 hover:bg-zinc-700 text-red-400 flex items-center gap-2 transition-colors"
                onClick={() => {
                  onBinDelete?.(contextMenu.binId!);
                  setContextMenu(null);
                }}
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Asset Card ─────────────────────────────────────────────────────────────

interface BinAssetCardProps {
  asset: Asset;
  isSelected?: boolean;
  onSelect?: () => void;
  onDelete: () => void;
  onDragStart: () => void;
}

function BinAssetCard({ asset, isSelected, onSelect, onDelete, onDragStart }: BinAssetCardProps) {
  const Icon = getAssetIcon(asset.type);
  const gradient = getAssetGradient(asset.type);

  const handleDragStart = useCallback((e: React.DragEvent) => {
    e.dataTransfer.setData('application/x-hyperedit-asset', JSON.stringify(asset));
    e.dataTransfer.effectAllowed = 'copy';
    onDragStart();
  }, [asset, onDragStart]);

  const handleClick = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    onSelect?.();
  }, [onSelect]);

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      onClick={handleClick}
      className={`group relative aspect-video bg-zinc-800 rounded-lg overflow-hidden cursor-grab active:cursor-grabbing border transition-colors ${
        isSelected
          ? 'border-orange-500 ring-2 ring-orange-500/30'
          : 'border-zinc-700/50 hover:border-orange-500/50'
      }`}
    >
      {asset.thumbnailUrl ? (
        <img
          src={asset.thumbnailUrl}
          alt={asset.filename}
          className="w-full h-full object-cover"
          draggable={false}
        />
      ) : (
        <div className={`w-full h-full bg-gradient-to-br ${gradient} flex items-center justify-center`}>
          <Icon className="w-7 h-7 text-white/80" />
        </div>
      )}

      {/* Type badge */}
      <div className={`absolute top-1 left-1 px-1.5 py-0.5 rounded bg-gradient-to-r ${gradient} text-[9px] font-medium uppercase`}>
        {asset.type}
      </div>

      {/* AI badge */}
      {asset.aiGenerated && (
        <div className="absolute top-1 left-[52px] px-1.5 py-0.5 rounded bg-gradient-to-r from-purple-500 to-pink-500 text-[9px] font-medium flex items-center gap-0.5">
          <Sparkles className="w-2.5 h-2.5" />
          AI
        </div>
      )}

      {/* Info bar */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 py-1">
        <div className="text-[10px] text-white truncate">{asset.filename}</div>
        <div className="text-[9px] text-zinc-400">
          {asset.type !== 'image' && formatDuration(asset.duration)}
          {asset.type !== 'image' && ' · '}
          {formatSize(asset.size)}
        </div>
      </div>

      {/* Delete button */}
      <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="p-1 bg-red-500/80 hover:bg-red-500 rounded"
          title="Delete"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

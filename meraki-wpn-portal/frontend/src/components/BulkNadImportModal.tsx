import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  X,
  Server,
  CheckSquare,
  Square,
  MinusSquare,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import {
  getIPSKOptions,
  getMerakiNetworkDevices,
  bulkCreateNads,
  type MerakiDevice,
  type BulkNadCreate,
  type BulkNadResult,
} from '../api/client'

interface BulkNadImportModalProps {
  onClose: () => void
  onImport: () => void
}

export default function BulkNadImportModal({ onClose, onImport }: BulkNadImportModalProps) {
  const [selectedNetwork, setSelectedNetwork] = useState('')
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set())
  const [sharedSecret, setSharedSecret] = useState('')
  const [nasType, setNasType] = useState('other')
  const [searchFilter, setSearchFilter] = useState('')
  const [importResult, setImportResult] = useState<BulkNadResult | null>(null)

  // Fetch available networks
  const { data: options, isLoading: optionsLoading } = useQuery({
    queryKey: ['ipsk-options'],
    queryFn: getIPSKOptions,
  })

  // Fetch devices for selected network
  const { data: devicesData, isLoading: devicesLoading } = useQuery({
    queryKey: ['network-devices', selectedNetwork],
    queryFn: () => getMerakiNetworkDevices(selectedNetwork),
    enabled: !!selectedNetwork,
  })

  const devices = devicesData?.devices || []

  // Filter devices by search term and type
  const filteredDevices = devices.filter((device) => {
    const matchesSearch =
      !searchFilter ||
      device.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      device.serial.toLowerCase().includes(searchFilter.toLowerCase()) ||
      device.model.toLowerCase().includes(searchFilter.toLowerCase())
    return matchesSearch && device.lanIp // Only show devices with LAN IP
  })

  // Bulk import mutation
  const importMutation = useMutation({
    mutationFn: (bulkData: BulkNadCreate) => bulkCreateNads(bulkData),
    onSuccess: (result) => {
      setImportResult(result)
      if (result.created.length > 0) {
        setTimeout(() => {
          onImport()
        }, 2000)
      }
    },
  })

  // Toggle device selection
  const toggleDevice = (serial: string) => {
    const newSelected = new Set(selectedDevices)
    if (newSelected.has(serial)) {
      newSelected.delete(serial)
    } else {
      newSelected.add(serial)
    }
    setSelectedDevices(newSelected)
  }

  // Select all filtered devices
  const selectAll = () => {
    const newSelected = new Set<string>()
    filteredDevices.forEach((dev) => newSelected.add(dev.serial))
    setSelectedDevices(newSelected)
  }

  // Select only APs
  const selectAPs = () => {
    const newSelected = new Set<string>()
    filteredDevices
      .filter((dev) => dev.model.toUpperCase().includes('MR') || dev.model.toUpperCase().includes('AP'))
      .forEach((dev) => newSelected.add(dev.serial))
    setSelectedDevices(newSelected)
  }

  // Select only switches
  const selectSwitches = () => {
    const newSelected = new Set<string>()
    filteredDevices
      .filter((dev) => dev.model.toUpperCase().includes('MS') || dev.model.toUpperCase().includes('SWITCH'))
      .forEach((dev) => newSelected.add(dev.serial))
    setSelectedDevices(newSelected)
  }

  // Clear selection
  const clearSelection = () => {
    setSelectedDevices(new Set())
  }

  // Handle import
  const handleImport = () => {
    if (!selectedNetwork || selectedDevices.size === 0 || !sharedSecret) {
      return
    }

    const bulkData: BulkNadCreate = {
      network_id: selectedNetwork,
      device_serials: Array.from(selectedDevices),
      shared_secret: sharedSecret,
      nas_type: nasType,
    }

    importMutation.mutate(bulkData)
  }

  // Generate random secret
  const generateSecret = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()'
    let secret = ''
    for (let i = 0; i < 32; i++) {
      secret += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    setSharedSecret(secret)
  }

  // Reset when network changes
  useEffect(() => {
    setSelectedDevices(new Set())
    setImportResult(null)
  }, [selectedNetwork])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Server className="text-meraki-blue" size={24} />
              Bulk Import NADs from Meraki
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Select devices from your Meraki network to create RADIUS clients
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!importResult ? (
            <>
              {/* Network Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Select Network
                </label>
                <select
                  value={selectedNetwork}
                  onChange={(e) => setSelectedNetwork(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                  disabled={optionsLoading}
                >
                  <option value="">Select a network...</option>
                  {options?.networks.map((network) => (
                    <option key={network.id} value={network.id}>
                      {network.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Shared Secret */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Shared Secret (same for all devices)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={sharedSecret}
                    onChange={(e) => setSharedSecret(e.target.value)}
                    placeholder="Enter shared secret"
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                  />
                  <button
                    type="button"
                    onClick={generateSecret}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg transition-colors"
                  >
                    Generate
                  </button>
                </div>
              </div>

              {/* NAS Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  NAS Type
                </label>
                <select
                  value={nasType}
                  onChange={(e) => setNasType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                >
                  <option value="other">Other</option>
                  <option value="cisco">Cisco</option>
                  <option value="meraki">Meraki</option>
                </select>
              </div>

              {/* Device Selection */}
              {selectedNetwork && (
                <>
                  {/* Quick Filters */}
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={selectAll}
                      className="px-3 py-1.5 text-sm bg-meraki-blue text-white rounded hover:bg-meraki-blue-dark transition-colors"
                    >
                      Select All ({filteredDevices.length})
                    </button>
                    <button
                      onClick={selectAPs}
                      className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      Select APs
                    </button>
                    <button
                      onClick={selectSwitches}
                      className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      Select Switches
                    </button>
                    <button
                      onClick={clearSelection}
                      className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      Clear
                    </button>
                    <div className="ml-auto text-sm text-gray-600 dark:text-gray-400 flex items-center">
                      Selected: <strong className="ml-1">{selectedDevices.size}</strong>
                    </div>
                  </div>

                  {/* Search */}
                  <div>
                    <input
                      type="text"
                      placeholder="Search devices by name, serial, or model..."
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-meraki-blue focus:border-transparent dark:bg-gray-700 dark:text-white"
                    />
                  </div>

                  {/* Devices Table */}
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                    {devicesLoading ? (
                      <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                        Loading devices...
                      </div>
                    ) : filteredDevices.length === 0 ? (
                      <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                        No devices found with LAN IP addresses
                      </div>
                    ) : (
                      <div className="max-h-96 overflow-y-auto">
                        <table className="w-full">
                          <thead className="bg-gray-50 dark:bg-gray-900 sticky top-0">
                            <tr>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                <button onClick={selectAll} className="hover:text-gray-700 dark:hover:text-gray-200">
                                  {selectedDevices.size === filteredDevices.length ? (
                                    <CheckSquare size={18} />
                                  ) : selectedDevices.size > 0 ? (
                                    <MinusSquare size={18} />
                                  ) : (
                                    <Square size={18} />
                                  )}
                                </button>
                              </th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                Device
                              </th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                Model
                              </th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                IP Address
                              </th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                Serial
                              </th>
                            </tr>
                          </thead>
                          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                            {filteredDevices.map((device) => (
                              <tr
                                key={device.serial}
                                className="hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                                onClick={() => toggleDevice(device.serial)}
                              >
                                <td className="px-4 py-3">
                                  <button onClick={(e) => {
                                    e.stopPropagation()
                                    toggleDevice(device.serial)
                                  }}>
                                    {selectedDevices.has(device.serial) ? (
                                      <CheckSquare size={18} className="text-meraki-blue" />
                                    ) : (
                                      <Square size={18} className="text-gray-400" />
                                    )}
                                  </button>
                                </td>
                                <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white">
                                  {device.name}
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                                  {device.model}
                                </td>
                                <td className="px-4 py-3 text-sm font-mono text-gray-600 dark:text-gray-400">
                                  {device.lanIp || 'N/A'}
                                </td>
                                <td className="px-4 py-3 text-sm font-mono text-gray-500 dark:text-gray-500">
                                  {device.serial}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          ) : (
            /* Import Results */
            <div className="space-y-4">
              <div className="text-center py-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Import Complete
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {importResult.created.length} created, {importResult.skipped.length} skipped,{' '}
                  {importResult.failed.length} failed
                </p>
              </div>

              {/* Created */}
              {importResult.created.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-2 font-medium text-green-600 dark:text-green-400 mb-2">
                    <CheckCircle size={18} />
                    Successfully Created ({importResult.created.length})
                  </h4>
                  <div className="space-y-2">
                    {importResult.created.map((nad) => (
                      <div
                        key={nad.serial}
                        className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded"
                      >
                        <div className="text-sm font-medium text-green-900 dark:text-green-300">
                          {nad.name}
                        </div>
                        <div className="text-xs text-green-700 dark:text-green-400">
                          {nad.ip} • {nad.model}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Skipped */}
              {importResult.skipped.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-2 font-medium text-yellow-600 dark:text-yellow-400 mb-2">
                    <AlertCircle size={18} />
                    Skipped ({importResult.skipped.length})
                  </h4>
                  <div className="space-y-2">
                    {importResult.skipped.map((nad, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded"
                      >
                        <div className="text-sm font-medium text-yellow-900 dark:text-yellow-300">
                          {nad.name}
                        </div>
                        <div className="text-xs text-yellow-700 dark:text-yellow-400">
                          {nad.reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Failed */}
              {importResult.failed.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-2 font-medium text-red-600 dark:text-red-400 mb-2">
                    <XCircle size={18} />
                    Failed ({importResult.failed.length})
                  </h4>
                  <div className="space-y-2">
                    {importResult.failed.map((nad, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded"
                      >
                        <div className="text-sm font-medium text-red-900 dark:text-red-300">
                          {nad.name}
                        </div>
                        <div className="text-xs text-red-700 dark:text-red-400">
                          {nad.error}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-6 border-t border-gray-200 dark:border-gray-700">
          {!importResult ? (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleImport}
                disabled={
                  !selectedNetwork ||
                  selectedDevices.size === 0 ||
                  !sharedSecret ||
                  importMutation.isPending
                }
                className="px-4 py-2 bg-meraki-blue text-white rounded-lg hover:bg-meraki-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {importMutation.isPending ? (
                  <>
                    <RefreshCw className="animate-spin" size={16} />
                    Creating NADs...
                  </>
                ) : (
                  <>
                    <Server size={16} />
                    Create {selectedDevices.size} NAD{selectedDevices.size !== 1 ? 's' : ''}
                  </>
                )}
              </button>
            </>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-meraki-blue text-white rounded-lg hover:bg-meraki-blue-dark transition-colors"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

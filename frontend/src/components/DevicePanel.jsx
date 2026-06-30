export default function DevicePanel({ devices, currentDevice, onSendTo }) {
  if (devices.length <= 1) return null
  return (
    <div className="device-panel">
      <div className="device-label">УСТРОЙСТВА ОНЛАЙН</div>
      <div className="device-list">
        {devices.map(d => (
          <div key={d} className={`device-item ${d === currentDevice ? 'me' : ''}`}>
            <span>{d === currentDevice ? `${d} (я)` : d}</span>
            {d !== currentDevice && (
              <button className="btn-send-to" onClick={() => onSendTo(d)}>→</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

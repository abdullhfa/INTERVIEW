import React, { useState, useEffect } from 'react';
import type { AudioDevice } from '../../types';

const MEETING_PLATFORMS = [
  { value: 'Zoom', label: 'Zoom' },
  { value: 'Microsoft Teams', label: 'Microsoft Teams' },
  { value: 'Google Meet', label: 'Google Meet' },
  { value: 'Webex', label: 'Webex' },
  { value: 'Skype', label: 'Skype' },
  { value: 'متصفح الويب', label: 'متصفح الويب' },
  { value: 'أخرى', label: 'أخرى' },
] as const;

interface AudioConfigModalProps {
  onStart: (
    micIdx: number | null,
    loopbackIdx: number | null,
    meetingPlatform: string,
  ) => void;
  onCancel: () => void;
}

export function AudioConfigModal({ onStart, onCancel }: AudioConfigModalProps) {
  const [loopbacks, setLoopbacks] = useState<AudioDevice[]>([]);
  
  const [selectedLoopback, setSelectedLoopback] = useState<number | null>(null);
  const [meetingPlatform, setMeetingPlatform] = useState('Zoom');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/audio/devices')
      .then(res => res.json())
      .then(data => {
        const loopbacksData = data.loopbacks || [];
        
        setLoopbacks(loopbacksData);
        
        // Null tells the backend to follow the current Windows default output.
        // Selecting the first enumerated device is unreliable when headphones
        // and speakers are both present.
        setSelectedLoopback(null);

        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load audio devices", err);
        setLoopbacks([]);
        setLoading(false);
      });
  }, []);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="audio-modal-title">
      <div className="modal-card">
        <h2 id="audio-modal-title">اختر صوت الاجتماع</h2>
        
        {loading ? (
          <p>جاري تحميل الأجهزة...</p>
        ) : (
          <div className="flex flex-col gap-4">
            {loopbacks.length === 0 && (
              <p style={{ color: 'var(--color-danger)' }}>
                لم يتم العثور على جهاز صوت نظام (loopback). لا يمكن بدء اكتشاف الأسئلة المباشر.
              </p>
            )}
            <div className="flex flex-col gap-2">
              <label className="text-sm text-muted" htmlFor="meeting-platform">
                برنامج الاجتماع
              </label>
              <select
                id="meeting-platform"
                className="input-field"
                value={meetingPlatform}
                onChange={(e) => setMeetingPlatform(e.target.value)}
                aria-label="برنامج الاجتماع"
              >
                {MEETING_PLATFORMS.map((platform) => (
                  <option key={platform.value} value={platform.value}>
                    {platform.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm text-muted" htmlFor="loopback-device">
                جهاز إخراج الصوت
              </label>
              <select 
                id="loopback-device"
                className="input-field" 
                value={selectedLoopback ?? ''} 
                onChange={(e) => setSelectedLoopback(
                  e.target.value === '' ? null : Number(e.target.value)
                )}
                aria-label="صوت المحاور"
              >
                <option value="">إخراج Windows الافتراضي (موصى به)</option>
                {loopbacks.map(l => (
                  <option key={l.index} value={l.index}>
                    {l.name}{l.is_default ? ' — الافتراضي الحالي' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel}>إلغاء</button>
          <button 
            className="btn btn-primary" 
            onClick={() => onStart(null, selectedLoopback, meetingPlatform)}
            disabled={loading || loopbacks.length === 0}
          >
            بدء الجلسة
          </button>
        </div>
      </div>
    </div>
  );
}

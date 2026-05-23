// src/test/App.test.tsx
import '@testing-library/jest-dom';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';

window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock the WebSocket API to intercept and simulate backend behavior
class MockWebSocket {
  url: string;
  readyState: number;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  onopen: (() => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    this.readyState = WebSocket.OPEN;
    this.send = vi.fn();
    this.close = vi.fn(() => {
      if (this.onclose) this.onclose();
    });
    // Expose the instance globally so the test environment can trigger events
    (globalThis as any).mockWsInstance = this;
  }
}

// Override the native WebSocket
globalThis.WebSocket = MockWebSocket as any;

describe('Anonymous Chat Room User Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should complete the full lifecycle: join, send, verify read receipts, and disconnect', async () => {
    render(<App />);

    // --- Step 1: Input callsign ---
    // Ensure no default credentials exist by enforcing manual input
    const testCallsign = 'Jasper'; 
    const callsignInput = screen.getByPlaceholderText('e.g. Jasper');
    fireEvent.change(callsignInput, { target: { value: testCallsign } });

    // --- Step 2: Join the chat room ---
    const joinButton = screen.getByText('Enter Chat');
    fireEvent.click(joinButton);

    // Simulate successful WebSocket connection
    act(() => {
      (globalThis as any).mockWsInstance.onopen();
    });

    // Verify the UI transitions to the chat interface
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();

    // --- Step 3: Input and send a message ---
    const testMessage = 'Hello NYCU!';
    const messageInput = screen.getByPlaceholderText('Type your message...');
    fireEvent.change(messageInput, { target: { value: testMessage } });

    // Submit the form
    const form = messageInput.closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    // Verify the WebSocket sent the correct JSON payload
    expect((globalThis as any).mockWsInstance.send).toHaveBeenCalledWith(
      JSON.stringify({ action: 'sendMessage', text: testMessage })
    );

    // --- Step 4: Verify Timestamp and Message Rendering ---
    // Simulate receiving the broadcasted message from the server
    const mockTimestamp = new Date().toISOString();
    act(() => {
      (globalThis as any).mockWsInstance.onmessage({
        data: JSON.stringify({
          type: 'message',
          messageId: 'msg-001',
          callsign: testCallsign,
          text: testMessage,
          timestamp: mockTimestamp,
          readBy: []
        })
      });
    });

    // Verify the message text is rendered
    expect(screen.getByText(testMessage)).toBeInTheDocument();

    // Verify the timestamp is rendered in HH:MM format
    const expectedTimeStr = new Date(mockTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    expect(screen.getByText(expectedTimeStr)).toBeInTheDocument();

    // --- Step 5: Verify Read Receipts ---
    // Simulate receiving a read receipt broadcast from another user
    act(() => {
      (globalThis as any).mockWsInstance.onmessage({
        data: JSON.stringify({
          type: 'read_receipt',
          messageId: 'msg-001',
          reader: 'Alice'
        })
      });
    });

    // Verify the read count UI updates correctly
    expect(screen.getByText('Read 1')).toBeInTheDocument();

    // --- Step 6: Safely Disconnect ---
    const leaveButton = screen.getByTitle('Leave Chat');
    fireEvent.click(leaveButton);

    // Verify WebSocket close method was triggered
    expect((globalThis as any).mockWsInstance.close).toHaveBeenCalled();

    // Verify the UI returns to the authentication screen
    expect(screen.getByText('Portal Access')).toBeInTheDocument();
  });
});
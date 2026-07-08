// Typed messages exchanged between the side panel and the content script.

export interface ExtractDocMessage {
  type: 'JALEBI_EXTRACT_DOC';
}

export interface OpenPanelMessage {
  type: 'JALEBI_OPEN_PANEL';
}

export type JalebiMessage = ExtractDocMessage | OpenPanelMessage;

export interface DocPayload {
  ok: boolean;
  docId?: string;
  title?: string;
  text?: string;
  url?: string;
  error?: string;
}

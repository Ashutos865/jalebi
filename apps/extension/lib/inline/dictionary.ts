// Personal dictionary — words the user has told Jalebi to stop flagging. Stored
// in chrome.storage.local so it follows them across every site and field.

export const DICT_KEY = 'jalebi.dict';

export async function loadDict(): Promise<Set<string>> {
  try {
    const s = await chrome.storage.local.get(DICT_KEY);
    return new Set<string>((s[DICT_KEY] as string[]) ?? []);
  } catch {
    return new Set<string>();
  }
}

export async function addWord(word: string): Promise<void> {
  const w = word.trim().toLowerCase();
  if (!w) return;
  try {
    const s = await chrome.storage.local.get(DICT_KEY);
    const set = new Set<string>((s[DICT_KEY] as string[]) ?? []);
    set.add(w);
    await chrome.storage.local.set({ [DICT_KEY]: [...set] });
  } catch {
    /* extension reloaded — ignore */
  }
}

/** Subscribe to dictionary changes; returns an unsubscribe fn. */
export function onDictChange(cb: (dict: Set<string>) => void): () => void {
  const handler = (
    changes: Record<string, chrome.storage.StorageChange>,
    area: string,
  ) => {
    if (area === 'local' && DICT_KEY in changes) {
      cb(new Set<string>((changes[DICT_KEY].newValue as string[]) ?? []));
    }
  };
  chrome.storage.onChanged.addListener(handler);
  return () => chrome.storage.onChanged.removeListener(handler);
}

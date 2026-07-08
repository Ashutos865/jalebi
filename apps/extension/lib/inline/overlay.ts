// A fixed, click-through layer that draws underlines under flagged spans.

export interface Underline {
  rect: DOMRect;
  color: string;
}

export class UnderlineLayer {
  private layer: HTMLDivElement;

  constructor() {
    this.layer = document.createElement('div');
    Object.assign(this.layer.style, {
      position: 'fixed',
      left: '0',
      top: '0',
      width: '0',
      height: '0',
      pointerEvents: 'none',
      zIndex: '2147483646',
    } as CSSStyleDeclaration);
    document.body.appendChild(this.layer);
  }

  draw(underlines: Underline[]): void {
    this.layer.textContent = '';
    for (const u of underlines) {
      const mark = document.createElement('div');
      Object.assign(mark.style, {
        position: 'fixed',
        left: `${u.rect.left}px`,
        top: `${u.rect.top}px`,
        width: `${u.rect.width}px`,
        height: `${u.rect.height}px`,
        borderBottom: `2px solid ${u.color}`,
        boxSizing: 'border-box',
        pointerEvents: 'none',
      } as CSSStyleDeclaration);
      this.layer.appendChild(mark);
    }
  }

  clear(): void {
    this.layer.textContent = '';
  }

  destroy(): void {
    this.layer.remove();
  }
}

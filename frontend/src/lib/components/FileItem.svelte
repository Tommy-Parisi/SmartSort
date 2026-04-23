<script lang="ts">
  export let name: string;
  export let extension: string = '';

  const ext = extension.toLowerCase().replace('.', '') || name.split('.').pop()?.toLowerCase() || '';

  const badges: Record<string, { bg: string; color: string }> = {
    pdf:  { bg: '#FAECE7', color: '#712B13' },
    docx: { bg: '#E6F1FB', color: '#0C447C' },
    doc:  { bg: '#E6F1FB', color: '#0C447C' },
    js:   { bg: '#EAF3DE', color: '#27500A' },
    ts:   { bg: '#EAF3DE', color: '#27500A' },
    jsx:  { bg: '#EAF3DE', color: '#27500A' },
    tsx:  { bg: '#EAF3DE', color: '#27500A' },
    csv:  { bg: '#FAEEDA', color: '#633806' },
    xlsx: { bg: '#FAEEDA', color: '#633806' },
    xls:  { bg: '#FAEEDA', color: '#633806' },
    pptx: { bg: '#FBEAF0', color: '#72243E' },
    ppt:  { bg: '#FBEAF0', color: '#72243E' },
    py:   { bg: '#E1F5EE', color: '#085041' },
  };

  const badge = badges[ext] ?? { bg: '#F1EFE8', color: '#444441' };
</script>

<div class="file-item">
  <span class="badge" style="background:{badge.bg}; color:{badge.color}">
    {ext || '?'}
  </span>
  <span class="name">{name}</span>
</div>

<style>
  .file-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
  }

  .badge {
    font-size: 10px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    text-transform: lowercase;
    flex-shrink: 0;
    min-width: 28px;
    text-align: center;
  }

  .name {
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>

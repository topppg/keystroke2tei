# Editor Notes

## Editor notes `<note>`

Once the writing process is encoded, and visualised with the 'Standard visualisation' view in Keystroke Loxensis, the writing process can be analysed. At this point, some particular writing actions, or other moments in the writing process, may be valuable for the analysis. To bring these important moments across, editor notes can be encoded as well. With the **Annotation Visualization** option in Keystroke Loxensis, these notes can subsequently be shown.

## Editor notes `<notes>`

> `<notes>` are only encoded in the `<p type="notes">` at the bottom of the XML-document.

| Attribute | Value | Description |
| :--- | :--- | :--- |
| `@corresp` | `corresp="#"` | The `@corresp` attribute indicates the number of the note, to which the writing action can refer using `@ana` |

### Example 1

```xml
<p source="notes">
<note corresp="1">Is this the actual order of the applications in her dock? Why else would she have changed the order on the spur of the moment?</note>
<note corresp="2">In the next version, this should probably be changed into "And me?".</note>
</p>
```

## Writing action with `@ana`

| Attribute | Value | Description |
| :--- | :--- | :--- |
| `@ana` | `ana="#"` | The `@ana` attribute links to the related editor's note listed in `<p type="notes">` |

The `@ana` attribute can be used to link the note with the corresponding writing action. This attribute can be added to the `<add>`, `<del>` and `<mod>` elements.

### Example 2

```xml
<add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311" ana="1">Adobe Acrobat Reader, the Downloads folder, Bin.</mod>
<add seq="20230526083007" type="nt|continue" evidence="1206-1213" ana="2">And I?</add>
```

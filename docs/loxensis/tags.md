# The Tags

For encoding the keystroke logging data, only a limited number of tags from the [TEI Guidelines](https://tei-c.org) are needed. If started from the '[Start file](start-file)' only the following elements are needed:

| Syntax | Description |
|--------|-------------|
| `<p>` | All the text is encoded in one single `<p>` element (`<p source="keystroke">`), all the 'Focus events' in another `<p>` element (`<p source="sources">`), and all editor notes (annotations) in a separate `<p source="notes">` element. |
| `<seg>` | Every sentence is encoded with a `<seg>` element |
| `<lb/>` | Every 'Enter/Return' is encoded with the empty element `<lb/>` element |
| `<add>` | Every addition, including new text production, is encoded with a `<add>` element |
| `<del>` | Every deletion is encoded with a `<del>` element |
| `<mod>` | During the production of a sentence the author can decide to leave the sentence produced so far to make a revision elsewhere after which they return to the end of the sentence they were writing, this return to the unfinished sentence is encoded in `<mod>` elements |
| `<media>` | The `<media>` element is used to encode the 'Focus events', in order to include them in the sequentiality of the visualisations, they are encoded inside an `<add>` element. For sources, the `<add>` element is specified with the attribute `@type="focus"` |
| `<desc>` | The `<media>` element requires the `<desc>` element (nested in `<media>`) for the further description of the visited digital source |
| `<title>` | The `<title>` element is used to encode the title of the text, if any. |
| `<emph>` | The `<emph>` element (emphasized) is used to mark words or phrases which are stressed or emphasized for linguistic or rhetorical effect, it is specified using the `@rend` attribute |
| `<note>` | The `<note>` element is used to encode editor notes, with the attribute `@corresp` to link it to the corresponding writing action |

At the most basic level, digital writing only requires two writing operations: insertions and deletions. When text is typed in the word processor, the text is inserted (added); when the text is deleted using the backspace- or delete key character per character, or by selecting the to-be-deleted text and deleting it, the text is deleted. Yet, multiple types of these writing actions can be distinguished. This encoding manual builds upon the taxonomy by Lindgren and Sullivan (2006), which distinguishes between 'pre-contextual' revisions ("revisions made before an externalised context is completed") and 'contextual' revisions ("revisions made within a completed externalised context"; see Lindgren 2006, 159), and applies these types of revisions to the writing of a sentence. As such, contextual revisions indicate revisions made in a previously written sentence, and pre-contextual revisions, by contrast, indicate revisions made before a sentence is completed. By using these two revision types, the editorial interpretation remains as limited as possible. These revision types, and the other writing actions that can be encoded, will be detailed in the following sections.

---

## Additions `<add>`

The `<add>` element is used to encode different types of insertions: **textual** additions to the digital document.

There are three attributes that are **obligatory** when using `<add>` elements: `@seq`, `@type`, and `@evidence`.

### Obligatory attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp of the modification in the text |
| `@type` | | The `@type` attribute indicates the type of the addition |
| | `type="nt"` | Indicates new text production |
| | `type="pre-context"` | Indicates an addition that was made _before_ the sentence was finished |
| | `type="context"` | Indicates an addition that was made after the sentence was finished |
| | `type="typo"` | Indicates that the addition was triggered by a typo |
| | `type="translocation"` | Indicates that the addition was part of a relocation of the text segment |
| | `type="previousType\|continue"` | Indicates that the addition was interrupted by an immediate revision, without changing the cursor location, and is now continued |
| | `type="source"` | Indicates that text was added by pasting directly from a digital source (e.g. website, other digital document) |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### Optional attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@ana` | `ana="#"` | The `@ana` attribute links to the related editor's note listed in `<p type="notes">` (see [Editor notes](#editor-notes-note)) |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colon's from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss` (see Example 1).

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

There are **6** different addition types: adding new text, typo related additions, pre-contextual additions, contextual additions, additions related to a translocation, and copied text from digital sources.

#### New text

`<add type="nt">`: The use of a keystroke logger allows for an exact reconstruction of the textual development. This includes the moment a new sentence is produced. Therefore, the production of new sentences can be incorporated in the encoding (`@type="nt"`), to be able to differentiate between "new" and "old" sentences, and to see when and where in the text new text was being produced. Every sentence that has not been written in the text before, is to be regarded as new text.

In Example 1, the writer wrote the first sentence "The desktop: a wallpaper of a painting by Georgia O'Ke" after which she made a typo. The first part of this writing action is encoded with the `@type="nt"`.

##### Example 1

```xml
<add seq="20230526081925" type="nt" evidence="16-75">The desktop: a wallpaper of a painting by Georgia O'Ke<del seq="20230526081948" type="typo" evidence="76-77">ff</del></add><add seq="20230526081948" type="nt|continue" evidence="78-82">effe.</add>
```

After the immediate correction of the typo (deleting the 'ff'), the new text production is continued. Since the cursor was not relocated, the continuation of the text production is encoded with `<add type="nt|continue">`. In this way, the writing action itself will not be counted as another newly produced sentence.

#### Typo related addition

`<add type="typo">`: A large number of revisions in digital writing occur as a result of typographical errors. Within the scope of genetic criticism, such "typos" are not the most meaningful entities because they do not immediately affect the meaning of the text. Yet, the revision of typographical errors can also break the flow in writing and therefore influence the writing process. In order to be able to distinguish between revisions and typos, every typo is encoded with `@type="typo"`.

There are two ways typos can be corrected:

1. immediately using the backspace-key: in this case, only a typo-related deletion occurs, after which the author continues writing (as the typo in Example 1, see also [Deletions](#deletions-del)).
2. at a later moment: in this case, both a deletion and an addition occur. The deletion of the wrongly typed character and the addition of the correct one. This is when the `<add type="typo">` is used.

In Example 2, the writer first wrote "he says: ", but she of course wanted to start the sentence with a capital 'H'. She thus went back to the start of the sentence to first delete the 'h', and then type the 'H'. The typing of the 'H' is the typo related addition.

##### Example 2

```xml
<add seq="20230526082627" type="nt" evidence="922-931"><del seq="20230526082633" type="typo" evidence="935">h</del><add seq="20230526082633" type="typo" evidence="937">H</add>e says: </add>
```

These typo related additions can occur before the sentence is completely finished, or can already be made as the sentence is still in production.

#### Pre-contextual addition

`<add type="pre-context">`: Pre-contextual additions occur during writing, specifically, before a sentence has been completed. Most pre-contextual **revisions** are made as the writer decides that something needs to be adjusted in the moment of writing, and are therefore mostly represented as 'pre-contextual deletions' (See: [Deletions](#deletions-del)). In that case the writer immediately presses the backspace key to delete the just written text and then continues writing. The cursor is not relocated. As well as revising directly at the leading edge (the location in the text where new meaning is created), the writer can also perform a pre-contextual revision after relocating the cursor to a location earlier in the sentence in production, to make a revision before finishing the sentence at the end of the leading edge. In those cases, when an insertion is being made, it is a pre-contextual addition.

In Example 3, the writer started with writing "Microsoft Word, Notion,", then she relocated her cursor to the start of the sentence to add another opening of the sentence: "Finder, Cala". Then she corrected the typo, and continued finishing the pre-contextual addition: "endar, Safari, Microsoft Outlook" (`<add type="pre-context|continue">`).

##### Example 3

```xml
<add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311">Adobe Acrobat Reader, the Downloads folder, Bin.</mod>
```

#### Contextual addition

`<add type="context">`: Contextual revisions, as opposed to pre-contextual revisions, are those revisions that are made in the text that has already been written. In the case of contextual additions, the writer relocates the cursor to insert text in already written text, or it is part of a substitution (contextual deletion and contextual addition). Contextual additions can take place at any point after writing the text in question, such as immediately after the production of the sentence, or at a later stage.

In Example 4, the writer had previously written the sentence "The Print Layout, imitating paper." Later, after the sentence had already been finished, she decided to add "just" to the sentence.

##### Example 4

```xml
<seg><add seq="20230526082146" type="nt" evidence="342-377">The Print Layout, <add seq="20230526083451" type="context" evidence="1844-1848">just </add>imitating paper.</add></seg>
```

#### Translocation related addition

`<add type="translocation">`: Digital writing allows for easy relocating text elements, for example by using 'CTRL X' and 'CTRL V'. In the basis, the translocation is just a deletion of text in one location in the text, and adding it again at another location. To allow these movements of text to be included in the encoding, and differentiated from other revision types, the translocations are encoded using `@type="translocation"`, for both the deletion and the addition.

In Example 5, the writer relocated the short sentence "CTRL+S."

##### Example 5

```xml
<seg><add seq="20230526083311" type="translocation" evidence="1636">CTRL+S.</add></seg>
```

```xml
<seg><add seq="20230526083218" type="nt" evidence="1501-1510">Do not <del seq="20230526083221" type="pre-context" evidence="1511-1513">to </del></add><add seq="20230526083222" type="nt|continue" evidence="1514-1537">forget to save the file.</add></seg>
```

```xml
<seg><del seq="20230526083308" type="translocation" evidence="1628"><add seq="20230526083228" type="nt" evidence="1540-1548">CTRL+S.</add></del></seg>
```

#### Copied text from a digital source

`<add type="source">`: Since writers have access to the Internet and other digital sources during writing, they can also easily copy source material from these sources into their document. To account for these instances - to differentiate them from regular new text production - the copy-pasting from sources can be annotated using `<add type="source">`.

In Example 6, the writer found a quote online which she could use in her text. She copied it directly from the website and pasted it into the Word document.

##### Example 6

```xml
<add seq="20230526082703" type="source" evidence="971">Longhand isn't well suited to my way of writing. I tend to end up with dozens of pages of crossings-out and margin scribbles just to find one good paragraph, and it's easy to lose your train of thought, working like that.</add>
```

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

The number in every `@evidence` needs to be **unique**, each encoded writing operation will be identified using this number.

---

## Deletions `<del>`

All attributes listed below are **obligatory** when using `<del>` elements.

### Obligatory attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp of the modification in the text |
| `@type` | | The `@type` attribute indicates the type of the deletion |
| | `type="pre-context"` | Indicates a deletion that was made _before_ the sentence was finished |
| | `type="context"` | Indicates a deletion that was made after the sentence was finished |
| | `type="typo"` | Indicates that the deletion was triggered by a typo |
| | `type="translocation"` | Indicates that the deletion was part of a relocation of the text segment |
| | `type="previousType\|continue"` | Indicates that the deletion was interrupted by an immediate revision, without changing the cursor location, and is now continued |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colon's from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss` (see Example 1).

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

There are **4** different deletion types: typo related deletions, pre-contextual deletions, contextual deletions, and translocation related deletions.

#### Typo related deletion

`<del type="typo">`: A large number of revisions in digital writing occur as a result of typographical errors. Within the scope of genetic criticism, such "typos" are not the most meaningful entities because they do not immediately affect the meaning of the text. Yet, the revision of typographical errors can also break the flow in writing and therefore influence the writing process. In order to be able to distinguish between revisions and typos, every typo is encoded with `@type="typo"`.

There are two ways typos can be corrected:

1. immediately using the backspace-key: in this case, only a typo-related deletion occurs, after which the author continues writing.
2. at a later moment: in this case, both a deletion and an addition occur. The deletion of the wrongly typed character and the addition of the correct one using `<add type="typo">`.

In Example 1, the writer first wrote "he says: ", but she of course wanted to start the sentence with a capital 'H'. She thus went back to the start of the sentence to first delete the 'h', and then type the 'H'.

##### Example 1

```xml
<add seq="20230526082627" type="nt" evidence="922-931"><del seq="20230526082633" type="typo" evidence="935">h</del><add seq="20230526082633" type="typo" evidence="937">H</add>e says: </add>
```

##### Example 2

In this example, the writer produced "On the digital aper" but missed the 'p' key. She immediately deleted "aper" and continued, now correctly typing "paper."

```xml
<add seq="20230526082203" type="nt" evidence="380-398">On the digital <del seq="20230526082210" type="typo" evidence="399-402">aper</del></add><add seq="20230526082211" type="nt|continue" evidence="403-409">paper</add>
```

#### Pre-contextual deletion

`<del type="pre-context">`: Pre-contextual deletions occur during writing, specifically, before a sentence has been completed. Most pre-contextual revisions are made as the writer decides that something needs to be adjusted in the moment of writing. In that case the writer immediately presses the backspace key to delete the just written text and then continues writing. The cursor is not relocated.

In Example 3, the writer initially wrote "Does it make writing easier, or is this you" but deleted "you" and continued with "just a myth?"

##### Example 3

```xml
<add seq="20230526082358" type="nt" evidence="700-742">Does it make writing easier, or is this <del seq="20230526082408" type="pre-context" evidence="743-745">you</del></add><add seq="20230526082409" type="nt|continue" evidence="746-758">just a myth?</add>
```

#### Contextual deletion

`<del type="context">`: Contextual deletions, as opposed to pre-contextual deletions, are those deletions that are made in the text that has already been written. The writer relocates the cursor to delete text in already written text, or it is part of a substitution (contextual deletion and contextual addition). Contextual deletions can take place at any point after writing the text in question, such as immediately after the production of the sentence, or at a later stage.

In Example 4, the writer had previously composed a sentence. She subsequently returned to delete "thought" and replaced it with "used to think that."

##### Example 4

```xml
<add seq="20230526082847" type="nt" evidence="1043-1061">Louise Dought<del seq="20230526082854" type="typo" evidence="1062">l</del></add><add seq="20230526082854" type="nt|continue" evidence="1063-1085">y always <del seq="20230526083119" type="context" evidence="1336">thought </del><add seq="20230526083121" type="context" evidence="1338-1358">used to think that </add>she<del seq="20230526082904" type="typo" evidence="1086-1088">e n</del></add><add seq="20230526082905" type="nt|continue" evidence="1089-1124"> needed the <add seq="20230526082952" type="context" evidence="1189-1197">physical </add>connection to the paper.</add>
```

#### Translocation related deletion

`<del type="translocation">`: Digital writing allows for easy relocating text elements, for example by using 'CTRL X' and 'CTRL V'. In the basis, the translocation is just a deletion of text in one location in the text, and adding it again at another location. To allow these movements of text to be included in the encoding, and differentiated from other revision types, the translocations are encoded using `@type="translocation"`, for both the deletion and the addition.

In Example 5, the writer moved the sentence "CTRL+S." from one location to another using cut and paste operations.

##### Example 5

```xml
<seg><add seq="20230526083311" type="translocation" evidence="1636">CTRL+S.</add></seg>
```

```xml
<seg><add seq="20230526083218" type="nt" evidence="1501-1510">Do not <del seq="20230526083221" type="pre-context" evidence="1511-1513">to </del></add><add seq="20230526083222" type="nt|continue" evidence="1514-1537">forget to save the file.</add></seg>
```

```xml
<seg><del seq="20230526083308" type="translocation" evidence="1628"><add seq="20230526083228" type="nt" evidence="1540-1548">CTRL+S.</add></del></seg>
```

##### Example 6

```xml
<add seq="20230526082703" type="source" evidence="971">Longhand isn't well suited to my way of writing. I tend to end up with dozens of pages of crossings-out and margin scribbles just to find one good paragraph, and it's easy to lose your train of thought, working like that.</add>
```

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

The number in every `@evidence` needs to be **unique**, each encoded writing operation will be identified using this number.

---

## Returns to the leading edge `<mod>`

The `<mod>` element encodes returns to the leading edge -- instances where writers interrupt sentence completion to make modifications elsewhere, then return to finish the unfinished text.

### Attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp of the modification in the text |
| `@type` | `type="continue"` | Indicates return to leading edge |
| | `type="continue\|continue"` | Continuation after immediate revision without cursor relocation |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colon's from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss`.

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

According to Lindgren et al. (2019), the leading edge is "typically at the end of the text produced so far, but can also occur at the end of insertions within previously written text" (347). These continuations are distinguished from regular additions.

In Example 1, the writer returns to complete an interrupted sentence with `<mod type="continue">`.

#### Example 1

```xml
<seg><add seq="20230526083033" type="nt" evidence="1277-1293">My handwriting is </add><mod seq="20230526083139" type="continue" evidence="1362-1371">terrible.</mod></seg>
```

In Example 2, multiple continuations appear, including `type="continue|continue"` after an immediate correction.

#### Example 2

```xml
<seg><add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Oulook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311">Adobe Acrobat Reader, the Downloads folder, Bin.</mod></seg>
```

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

The number in every `@evidence` needs to be **unique**, each encoded writing operation will be identified using this number.

**Reference:** Lindgren, Eva, et al. 2019. "Revising at the Leading Edge: Shaping Ideas or Clearing up Noise." _Observing Writing_, edited by Lindgren and Kirk P.H. Sullivan, 346-65. Brill.

---

## Sources `<media>`

Online sources and websites visited during the writing process -- logged with Inputlog -- are encoded in a separate paragraph element: `<p source="sources">`. The `<media>` element captures these consulted sources according to TEI Guidelines, requiring a `<desc>` child element for source descriptions.

### Attributes for `<media>`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@url` | `url="Guardian"` | The specific url or name of the website visited |
| `@mimeType` | | The type of the source (e.g., Internet-page or local application) |

#### `@url`

The `@url` attribute provides the specific website URL if available, or the website name if the URL is unknown.

#### `@mimeType`

This attribute identifies the source type, such as Internet pages or local applications. Per TEI Guidelines, values can align with the MIME Media Type system defined by RFC 2046. The Internet Assigned Numbers Authority (IANA) maintains the official list.

### Attributes for `<add>` for the sources

The `<media>` element must be wrapped in an `<add>` element to record when the source was consulted, enabling replay functionality in Keystroke Loxensis.

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp indicating when the source was accessed |
| `@type` | `type="focus"` | Indicates that text was added by pasting directly from a digital source |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

#### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colon's from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss`.

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

#### `@type`

Use the value `"focus"` when adding the `<add>` element for source consultation moments.

#### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action. Each `@evidence` value must be unique, identifying each encoded writing operation.

### Example

```xml
<add seq="20230526082504" type="focus" evidence="831"><media url="Guardian" mimeType="Internet"><desc>Writers' desktops | Books | The Guardian - Google Chrome</desc></media></add>
<lb/> <add seq="20230526082507" type="focus" evidence="834"><media url="Guardian" mimeType="Internet"><desc>Steven Hall: My desktop | Fiction | The Guardian - Google Chrome</desc></media></add>
<lb/>
```

---

## Editor notes `<note>`

Once the writing process is encoded and visualized with the 'Standard visualisation' view in Keystroke Loxensis, analysis becomes possible. Editor notes can be encoded to highlight important moments in the writing process. These notes are displayable through the **Annotation Visualization** option in Keystroke Loxensis.

### Attributes for `<note>`

The `<note>` element is only encoded within the `<p source="notes">` section at the document's bottom.

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@corresp` | `corresp="#"` | Indicates the note number, allowing writing actions to reference it via `@ana` |

#### Example 1

```xml
<p source="notes">
  <note corresp="1">Is this the actual order of the applications in her dock? Why else would she have changed the order on the spur of the moment?</note>
  <note corresp="2">In the next version, this should probably be changed into "And me?".</note>
</p>
```

### Writing action with `@ana`

The `@ana` attribute links writing actions to their corresponding editor notes.

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@ana` | `ana="#"` | Links the note to the corresponding writing action in `<p type="notes">` |

This attribute can be applied to `<add>`, `<del>`, and `<mod>` elements.

#### Example 2

```xml
<add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311" ana="1">Adobe Acrobat Reader, the Downloads folder, Bin.</mod>

<add seq="20230526083007" type="nt|continue" evidence="1206-1213" ana="2">And I?</add>
```

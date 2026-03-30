# Encoding Overview

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding>

## Encoding manual for keystroke logging data

In order to use the Keystroke Loxensis as a visualisation tool of the writing process, the keystroke data has to be encoded into the text versions. This encoding manual explains the mandatory tags and attributes. For an elaborate discussion of the reasoning behind some parts of the encoding, see: [Bekius, Lamyk. 2021. 'The Reconstruction of the Author's Movement Through the Text, or How to Encode Keystroke Logged Writing Processes in TEI-XML'. *Variants*, 15-16: 3-43.](https://doi.org/10.4000/variants.1245)

### Table of contents

- [The start files](#the-start-files)
- [The tags](#the-tags)
  - [Additions](#additions-add)
  - [Deletions](#deletions-del)
  - [Returns to leading edge](#returns-to-the-leading-edge-mod)
  - [Sources](#sources-media)
  - [Editor notes](#editor-notes-note)
- [Example General Analysis](#example-general-analysis)
- [Example encoding](#example-encoding)

---

## The start files

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/start-file>

### What do you need for the encoding?

1. The most fine-grained analysis from the used keystroke logging tool, e.g. the General Analysis from [Inputlog](https://www.inputlog.net), or the Session Log from [GGXLog](https://www.ggxlog.net/index.php).
2. An XML editor.
3. Use the 'Start file' below as your basic template.

### Start file

```xml
<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title><!-- title of the text --></title>
                <author><!-- author of the text --></author>
            </titleStmt>
            <publicationStmt>
                <p corresp="session"><!-- # of the session --></p>
                <p corresp="version"><!-- # of the text-version --></p>
                <p corresp="total_versions"><!-- total # of versions or sessions --></p>
            </publicationStmt>
            <sourceDesc>
                <p>
                    <l><!-- Date of the writing session --></l>
                    <l><!-- Start-time of the writing session --></l>
                    <l><!-- Duration of the writing session --></l>
                </p>
                <p><!-- Give a description of the author here, the description given in the first session-file will be used in the about.html --></p>
            </sourceDesc>
        </fileDesc>
    </teiHeader>
    <text>
        <body>
            <p source="keystrokes">
                <!-- Encode the writing process of the text here -->
            </p>
            <p source="sources">
                <!-- Encode the sources here -->
            </p>
            <p source="notes">
                <!-- Encode possible editor notes here -->
            </p>
        </body>
    </text>
</TEI>
```

---

## The tags

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/the-tags>

For encoding keystroke logging data, only a limited number of tags from the TEI Guidelines are needed. If started from the 'Start file' only the following elements are needed:

| Syntax | Description |
|--------|-------------|
| `<p>` | All text is encoded in one single `<p>` element (`<p source="keystrokes">`), all the 'Focus events' in another `<p>` element (`<p source="sources">`), and all editor notes (annotations) in a separate `<p source="notes">` element. |
| `<seg>` | Every sentence is encoded with a `<seg>` element. |
| `<lb/>` | Every 'Enter/Return' is encoded with the empty element `<lb/>`. |
| `<add>` | Every addition, including new text production, is encoded with an `<add>` element. |
| `<del>` | Every deletion is encoded with a `<del>` element. |
| `<mod>` | During the production of a sentence the author can decide to leave the sentence produced so far to make a revision elsewhere after which they return to the end of the sentence they were writing, this return to the unfinished sentence is encoded in `<mod>` elements. |
| `<media>` | The `<media>` element is used to encode the 'Focus events', in order to include them in the sequentiality of the visualisations, they are encoded inside an `<add>` element. For sources, the `<add>` element is specified with the attribute `@type="focus"`. |
| `<desc>` | The `<media>` element requires the `<desc>` element (nested in `<media>`) for the further description of the visited digital source. |
| `<title>` | The `<title>` element is used to encode the title of the text, if any. |
| `<emph>` | The `<emph>` element (emphasized) is used to mark words or phrases which are stressed or emphasized for linguistic or rhetorical effect, it is specified using the `@rend` attribute. |
| `<note>` | The `<note>` element is used to encode editor notes, with the attribute `@corresp` to link it to the corresponding writing action. |

"At the most basic level, digital writing only requires two writing operations: insertions and deletions." The manual applies a taxonomy distinguishing between pre-contextual and contextual revisions as they apply to sentence writing, allowing "the editorial interpretation remains as limited as possible."

---

## Additions `<add>`

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/additions/>

The `<add>` element encodes textual insertions in digital documents. Three attributes are mandatory: `@seq`, `@type`, and `@evidence`.

### Attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhmmss"` | Timestamp of the modification |
| `@type` | Various (see below) | Type of addition |
| `@evidence` | `evidence="###"` | References the #id from General Analysis |
| `@ana` | `ana="#"` | (Optional) Links to editor's notes |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colons from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss`.

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action. Each encoded operation requires a unique number for identification purposes.

### `@type`

There are **6** different addition types:

#### New Text (`type="nt"`)

Encodes production of sentences not previously written in the text.

```xml
<add seq="20230526081925" type="nt" evidence="16-75">The desktop: a wallpaper of a painting by Georgia O'Ke<del seq="20230526081948" type="typo" evidence="76-77">ff</del></add><add seq="20230526081948" type="nt|continue" evidence="78-82">effe.</add>
```

#### Typo-Related Addition (`type="typo"`)

Distinguishes typographical error corrections from meaningful revisions. Occurs when errors are corrected after deletion.

```xml
<add seq="20230526082627" type="nt" evidence="922-931"><del seq="20230526082633" type="typo" evidence="935">h</del><add seq="20230526082633" type="typo" evidence="937">H</add>e says: </add>
```

#### Pre-Contextual Addition (`type="pre-context"`)

Insertions made during sentence composition, before completion.

```xml
<add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add>
```

#### Contextual Addition (`type="context"`)

Revisions inserted into already-written text, often part of substitutions.

```xml
<seg><add seq="20230526082146" type="nt" evidence="342-377">The Print Layout, <add seq="20230526083451" type="context" evidence="1844-1848">just </add>imitating paper.</add></seg>
```

#### Translocation-Related Addition (`type="translocation"`)

Text relocations using cut-and-paste operations.

```xml
<seg><add seq="20230526083311" type="translocation" evidence="1636">CTRL+S.</add></seg>
<seg><add seq="20230526083218" type="nt" evidence="1501-1510">Do not <del seq="20230526083221" type="pre-context" evidence="1511-1513">to </del></add><add seq="20230526083222" type="nt|continue" evidence="1514-1537">forget to save the file.</add></seg>
<seg><del seq="20230526083308" type="translocation" evidence="1628"><add seq="20230526083228" type="nt" evidence="1540-1548">CTRL+S.</add></del></seg>
```

#### Copied Text from Digital Source (`type="source"`)

Text pasted directly from external digital sources.

```xml
<add seq="20230526082703" type="source" evidence="971">Longhand isn't well suited to my way of writing. I tend to end up with dozens of pages of crossings-out and margin scribbles just to find one good paragraph, and it's easy to lose your train of thought, working like that.</add>
```

---

## Deletions `<del>`

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/deletions/>

All attributes listed below are **obligatory** when using `<del>` elements.

### Attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhmmss"` | The `@seq` attribute gives the value of the timestamp of the modification in the text |
| `@type` | | The `@type` attribute indicates the type of the deletion |
| | `type="pre-context"` | Indicates a deletion that was made _before_ the sentence was finished |
| | `type="context"` | Indicates a deletion that was made after the sentence was finished |
| | `type="typo"` | Indicates that the deletion was triggered by a typo |
| | `type="translocation"` | Indicates that the deletion was part of a relocation of the text segment |
| | `type="previousType\|continue"` | Indicates that the deletion was interrupted by an immediate revision, without changing the cursor location, and is now continued |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colons from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss`.

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

There are **4** different deletion types: typo related deletions, pre-contextual deletions, contextual deletions, and deletions related to a translocation.

#### Typo related deletion (`type="typo"`)

A large number of revisions in digital writing occur as a result of typographical errors. Within the scope of genetic criticism, such "typos" are not the most meaningful entities because they do not immediately affect the meaning of the text. Yet, the revision of typographical errors can also break the flow in writing and therefore influence the writing process. In order to be able to distinguish between revisions and typos, every typo is encoded with `@type="typo"`.

There are two ways typos can be corrected:

1. Immediately using the backspace-key: in this case, only a typo-related deletion occurs, after which the author continues writing.
2. At a later moment: in this case, both a deletion and an addition occur. The deletion of the wrongly typed character and the addition of the correct one. This is when the `<add type="typo">` is used (see also [Additions](#additions-add)).

**Example 1**: The writer first wrote "he says: ", but she wanted to start the sentence with a capital 'H'. She went back to the start of the sentence to first delete the 'h', and then type the 'H'. The deleting of the 'h' is the typo related deletion.

```xml
<add seq="20230526082627" type="nt" evidence="922-931"><del seq="20230526082633" type="typo" evidence="935">h</del><add seq="20230526082633" type="typo" evidence="937">H</add>e says: </add>
```

**Example 2**: The writer was producing a new sentence when she made a typo - "On the digital aper" - she missed the 'p'-key. She immediately noticed this, deleted "aper" - which is the typo related deletion - and continued writing.

```xml
<add seq="20230526082203" type="nt" evidence="380-398">On the digital <del seq="20230526082210" type="typo" evidence="399-402">aper</del></add><add seq="20230526082211" type="nt|continue" evidence="403-409">paper</add>
```

#### Pre-contextual deletion (`type="pre-context"`)

Pre-contextual deletions occur during writing, specifically, before a sentence has been completed. Most pre-contextual **revisions** are made as the writer decides that something needs to be adjusted in the moment of writing, and are therefore mostly represented as 'pre-contextual deletions'. In this case the writer immediately presses the backspace key to delete the just written text and then continues writing. The cursor is not relocated.

**Example 3**: The writer wrote "Does it make writing easier, or is this you". She then deleted "you", and continued writing "just a myth?"

```xml
<add seq="20230526082358" type="nt" evidence="700-742">Does it make writing easier, or is this <del seq="20230526082408" type="pre-context" evidence="743-745">you</del></add><add seq="20230526082409" type="nt|continue" evidence="746-758">just a myth?</add>
```

#### Contextual deletion (`type="context"`)

Contextual revisions, as opposed to pre-contextual revisions, are those revisions that are made in the text that has already been written. In the case of contextual additions, the writer relocates the cursor to insert text in already written text, or it is part of a substitution (contextual deletion and contextual addition). Contextual additions can take place at any point after writing the text in question, such as immediately after the production of the sentence, or at a later stage.

**Example 4**: The writer had previously written the sentence "Louise Doughty always thought that she needed the physical connection to the paper." The word "physical" was already added later (`<add type="context">`). After a short while, she returned to the sentence again to delete "thought", which is the contextual deletion (`<del type="context">`), and to replace it with "used to think that" (`<add type="context">`).

```xml
<add seq="20230526082847" type="nt" evidence="1043-1061">Louise Dought<del seq="20230526082854" type="typo" evidence="1062">l</del></add><add seq="20230526082854" type="nt|continue" evidence="1063-1085">y always <del seq="20230526083119" type="context" evidence="1336">thought </del><add seq="20230526083121" type="context" evidence="1338-1358">used to think that </add>she<del seq="20230526082904" type="typo" evidence="1086-1088">e n</del></add><add seq="20230526082905" type="nt|continue" evidence="1089-1124"> needed the <add seq="20230526082952" type="context" evidence="1189-1197">physical </add>connection to the paper.</add>
```

#### Translocation related deletion (`type="translocation"`)

Digital writing allows for easy relocating text elements, for example by using 'CTRL X' and 'CTRL V'. In the basis, the translocation is just a deletion of text in one location in the text, and adding it again at another location. To allow these movements of text to be included in the encoding, and differentiated from other revision types, the translocations are encoded using `@type="translocation"`, for both the deletion and the addition.

**Example 5**: The writer relocated the short sentence "CTRL+S." The deletion of this sentence is encoded with `<del type="translocation">`.

```xml
<seg><add seq="20230526083311" type="translocation" evidence="1636">CTRL+S.</add></seg>
<seg><add seq="20230526083218" type="nt" evidence="1501-1510">Do not <del seq="20230526083221" type="pre-context" evidence="1511-1513">to </del></add><add seq="20230526083222" type="nt|continue" evidence="1514-1537">forget to save the file.</add></seg>
<seg><del seq="20230526083308" type="translocation" evidence="1628"><add seq="20230526083228" type="nt" evidence="1540-1548">CTRL+S.</add></del></seg>
```

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

---

## Returns to the Leading Edge `<mod>`

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/returns/>

"Returns to the leading edge" occur when writers finish incomplete sentences after modifications elsewhere. Per Lindgren et al. (2019), the leading edge is "typically at the end of the text produced so far" but can occur within insertions where writers revise or expand ideas.

### Attributes

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhmmss"` | Timestamp of the modification |
| `@type` | `type="continue"` | Return to leading edge of sentence |
| | `type="continue\|continue"` | Continuation interrupted by immediate revision, now resumed |
| `@evidence` | `evidence="###"` | References the #id from General Analysis |

### `@seq`

The timestamp should be taken from the 'Event StartClock' column in General Analysis, formatted as `hhmmss` (removing colons). For multi-session processes, use `yyyymmddhhmmss` format. The attribute value must allow chronological ordering of writing actions. When simultaneous actions occur, XML tree order determines sequence; add one second to later actions if different ordering is needed.

### `@type`

**Example 1**: The writer began "My handwriting is", made modifications elsewhere, then returned to complete the sentence with "terrible."

```xml
<seg><add seq="20230526083033" type="nt" evidence="1277-1293">My handwriting is </add><mod seq="20230526083139" type="continue" evidence="1362-1371">terrible.</mod></seg>
```

**Example 2**: Writer began "Microsoft Word, Notion,", added pre-contextual content, then returned multiple times to complete the sentence with `continue` and `continue|continue` markers.

```xml
<seg><add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311">Adobe Acrobat Reader, the Downloads folder, Bin.</mod></seg>
```

### `@evidence`

The value references the 'Event id' number of the first pressed key in the writing action. Each encoded operation requires a **unique** number for identification purposes.

### Reference

Lindgren, Eva, et al. (2019). "Revising at the Leading Edge: Shaping Ideas or Clearing up Noise." *Observing Writing*, edited by Lindgren and Sullivan, 346-365. Brill.

---

## Sources `<media>`

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/sources/>

The `<media>` element encodes online sources and websites visited during the writing process that were logged with Inputlog. These are placed within a dedicated `<p source="sources">` element.

According to TEI Guidelines, `<media>` requires a `<desc>` child element containing the source description, such as website titles or application names.

### Attributes for `<media>`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@url` | `url="Guardian"` | Specifies the URL or website name visited |
| `@mimeType` | | Indicates the source type (Internet page, local application, etc.). Adheres to MIME Media Type standards defined by RFC 2046 and maintained by IANA. |

### Attributes for `<add>` wrapping sources

The `<media>` element should be wrapped in an `<add>` element to mark when the source was consulted, enabling replay functionality in Keystroke Loxensis.

| Attribute | Value | Description |
|-----------|-------|-------------|
| `@seq` | `seq="yyyymmddhhmmss"` | Timestamp of when source was consulted |
| `@type` | `type="focus"` | Indicates a focus event (source consultation) |
| `@evidence` | `evidence="###"` | References the event #id from General Analysis |

### Example

```xml
<add seq="20230526082504" type="focus" evidence="831"><media url="Guardian" mimeType="Internet"><desc>Writers' desktops | Books | The Guardian - Google Chrome</desc></media></add>
<lb/>
<add seq="20230526082507" type="focus" evidence="834"><media url="Guardian" mimeType="Internet"><desc>Steven Hall: My desktop | Fiction | The Guardian - Google Chrome</desc></media></add>
<lb/>
```

---

## Editor notes `<note>`

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/notes/>

Editor notes highlight important moments in the writing process for subsequent analysis using the Annotation Visualization feature. Notes are placed exclusively in a `<p source="notes">` section at the document's end. Each note receives a `@corresp` attribute with a number for cross-referencing.

Writing actions use the `@ana` attribute to connect with related editor notes. This attribute works with `<add>`, `<del>`, and `<mod>` elements.

### Example: notes section

```xml
<p source="notes">
<note corresp="1">Is this the actual order of the applications in her dock? Why else would she have changed the order on the spur of the moment?</note>
<note corresp="2">In the next version, this should probably be changed into "And me?".</note>
</p>
```

### Example: linking notes to writing actions via `@ana`

```xml
<add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311" ana="1">Adobe Acrobat Reader, the Downloads folder, Bin.</mod><add seq="20230526083007" type="nt|continue" evidence="1206-1213" ana="2">And I?</add>
```

---

## Example General Analysis

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/example>

This page presents a General Analysis table from Inputlog, showing the raw keystroke logging data that serves as input for the encoding. The table contains approximately 1,516 event rows capturing keyboard input, mouse movements, clicks, focus changes, insertions, and replacements across a writing session.

### Table columns

| Column | Description |
|--------|-------------|
| `event_type` | Categorizes actions (keyboard, mouse, focus, insert, replacement) |
| `event_id` | Sequential numbering of each recorded event |
| `event_output` | Text or action produced |
| `event_startClock` | Timestamp when event begins |
| `event_position` | Character position in document |
| `event_endClock` | Timestamp when event concludes |
| `event_pauseTime` | Duration between keystrokes (ms) |
| `event_doclength` | Document length at event point |
| `event_charProduction` | Characters added per event |

### Sample rows (first 20 of ~1,516)

| event_type | event_id | event_output | event_startClock | event_position | event_endClock | event_pauseTime | event_doclength | event_charProduction |
|---|---|---|---|---|---|---|---|---|
| focus | 0 | WordLog_Lamyk Bekius_20230526081824.docx | 00:00:00.375 | | 00:00:00.375 | 0 | | 0 |
| mouse | 1 | Movement | 00:00:00.375 | | 00:00:00.969 | 0 | | 0 |
| focus | 2 | Microsoft account privacy notice | 00:00:00.969 | | 00:00:00.969 | 0 | | 0 |
| mouse | 3 | Movement | 00:00:05.032 | | 00:00:07.766 | 4063 | | 0 |
| mouse | 4 | Movement | 00:00:10.610 | | 00:00:11.922 | 2844 | | 0 |
| mouse | 5 | LEFT Click | 00:00:12.157 | | 00:00:12.266 | 235 | | 0 |
| focus | 6 | WordLog_Lamyk Bekius_20230526081824.docx | 00:00:12.266 | | 00:00:12.266 | 0 | | 0 |
| mouse | 7 | Movement | 00:00:12.922 | | 00:00:14.453 | 656 | | 0 |
| mouse | 8 | Movement | 00:00:15.532 | | 00:00:16.391 | 1079 | | 0 |
| mouse | 9 | LEFT Click | 00:00:16.563 | | 00:00:17.078 | 172 | | 0 |
| mouse | 10 | Movement | 00:00:16.703 | | 00:00:17.032 | 375 | | 0 |
| mouse | 11 | Movement | 00:00:17.094 | | 00:00:22.157 | 62 | | 0 |
| mouse | 12 | LEFT Click | 00:00:22.438 | | 00:00:23.297 | 281 | | 0 |
| mouse | 13 | Movement | 00:00:22.532 | | 00:00:23.297 | 765 | | 0 |
| mouse | 14 | Movement | 00:00:23.313 | | 00:00:24.500 | 16 | | 0 |
| keyboard | 16 | T | 00:00:28.573 | 0 | 00:00:28.660 | 3875 | 1 | 1 |
| keyboard | 17 | h | 00:00:28.720 | 1 | 00:00:28.817 | 147 | 2 | 2 |
| keyboard | 18 | e | 00:00:28.837 | 2 | 00:00:28.909 | 117 | 3 | 3 |
| keyboard | 19 | SPACE | 00:00:29.067 | 3 | 00:00:29.178 | 230 | 4 | 4 |
| keyboard | 20 | d | 00:00:29.373 | 4 | 00:00:29.451 | 306 | 5 | 5 |

The full table is available at the [source page](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/example).

---

## Example encoding

> Source: <https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/example-xml>

The following is the complete TEI XML encoding of the example writing session:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
	<teiHeader>
		<fileDesc>
			<titleStmt>
				<title>Digital writing, forever</title> <!-- title of the text -->
				<author>Jane Doe</author> <!-- author of the text -->
				<respStmt>
					<name>Lamyk Bekius</name>
					<resp>encoding scheme, TEI customization, encoding</resp>
				</respStmt>
			</titleStmt>
			<publicationStmt>
				<p corresp="session">1</p> <!-- # of the session -->
				<p corresp="version">1</p> <!-- # of the text-version -->
				<p corresp="total_versions">1</p> <!-- total # of versions or sessions -->
			</publicationStmt>
			<sourceDesc>
				<p>
					<l>26-05-2023</l> <!-- Date of the writing session -->
					<l>08:35:05</l> <!-- Start-time of the writing session -->
					<l>00:16:10</l> <!-- Duration of the writing session -->
				</p>
				<p>This is an example of a keystroke-logged writing process to illustrate the use of Keystroke Loxensis Light. The writing process was logged with Inputlog.</p>
			</sourceDesc>
		</fileDesc>
	</teiHeader>
	<text>
		<body>
			<p source="keystrokes">  <!-- encode the writing process here -->
				<title>
					<add seq="20230526083413" type="nt" evidence="1800-1824">
						<emph rend="bold">Digital writing, forever.</emph>
						<lb/>
					</add>
				</title>
				<seg>
					<add seq="20230526083322" type="nt" evidence="1645-1683">On the desk: a bright yellow iMac</add>
				</seg>
				<seg>
					<add seq="20230526081925" type="nt" evidence="16-75">The desktop: a wallpaper of a painting by Georgia O'Ke<del seq="20230526081948" type="typo" evidence="76-77">ff</del></add><add seq="20230526081948" type="nt|continue" evidence="78-82">effe.</add>
				</seg>
				<seg>
					<add seq="20230526081955" type="nt" evidence="85-150">The dock: positioned on the left side of the screen.</add>
				</seg>
				<seg>
					<add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Outlook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311" ana="1">Adobe Acrobat Reader, the Downloads folder, Bin.</mod>
				</seg>
				<seg>
					<add seq="20230526082125" type="nt" evidence="314-339">Microsoft Word, now open.</add>
				</seg>
				<seg>
					<add seq="20230526082146" type="nt" evidence="342-377">The Print Layout, <add seq="20230526083451" type="context" evidence="1844-1848">just </add>imitating paper.</add>
				</seg>
				<seg>
					<add seq="20230526082203" type="nt" evidence="380-398">On the digital <del seq="20230526082210" type="typo" evidence="399-402">aper</del>
					</add>
					<add seq="20230526082211" type="nt|continue" evidence="403-409">paper<del seq="20230526082226" type="pre-context" evidence="410-411">, </del>
					</add>
					<add seq="20230526082226" type="nt|continue" evidence="412-492"> the cursor blinks, happily, but also urging, encouraging, <emph rend="italics">demanding</emph> me to write.</add>
				</seg>
				<seg>
					<add seq="20230526082259" type="nt" evidence="495-513">But what to write?</add>
				</seg>
				<seg>
					<add seq="20230526082310" type="nt" evidence="516-615">It should be a short text for illustrating purposes, but even then you have find the right words.</add>
				</seg>
				<seg>
					<add seq="20230526082436" type="nt" evidence="767-828">That remains a fact, both with writing on paper and digitally.</add>
				</seg>
				<seg>
					<add seq="20230526082339" type="nt" evidence="618-645">How do other writers do it?</add>
				</seg>
				<seg>
					<add seq="20230526082346" type="nt" evidence="648-697">And how do they feel about writing on a computer?</add>
				</seg>
				<seg>
					<add seq="20230526082358" type="nt" evidence="700-742">Does it make writing easier, or is this <del seq="20230526082408" type="pre-context" evidence="743-745">you</del>
					</add>
					<add seq="20230526082409" type="nt|continue" evidence="746-758">just a myth?</add>
				</seg>
				<seg>
					<add seq="20230526082610" type="nt" evidence="867-919">Steven Hall always works straight onto the computer.</add>
				</seg>
				<seg>
					<add seq="20230526082627" type="nt" evidence="922-931"><del seq="20230526082633" type="typo" evidence="935">h</del><add seq="20230526082633" type="typo" evidence="937">H</add>e says: </add><add seq="20230526082718" type="context" evidence="993">"</add><add seq="20230526082703" type="source" evidence="971">Longhand isn't well suited to my way of writing. <seg>I tend to end up with dozens of pages of crossings-out and margin scribbles just to find one good paragraph, and it's easy to lose your train of thought, working like that.<add seq="20230526082722" type="context" evidence="998">"</add>
						</seg>
					</add>
				</seg>
				<seg>
					<add seq="20230526082847" type="nt" evidence="1043-1061">Louise Dought<del seq="20230526082854" type="typo" evidence="1062">l</del></add><add seq="20230526082854" type="nt|continue" evidence="1063-1085">y always <del seq="20230526083119" type="context" evidence="1336">thought </del><add seq="20230526083121" type="context" evidence="1338-1358">used to think that </add>she<del seq="20230526082904" type="typo" evidence="1086-1088">e n</del></add><add seq="20230526082905" type="nt|continue" evidence="1089-1124"> needed the <add seq="20230526082952" type="context" evidence="1189-1197">physical </add>connection to the paper.</add>
				</seg>
				<seg>
					<add seq="20230526082917" type="nt" evidence="1127-1131">Now<add seq="20230526082942" type="context" evidence="1173-1182">, however, </add> <del seq="20230526082921" type="pre-context" evidence="1132">h</del></add><add seq="20230526082921" type="nt|continue" evidence="1133-1168">she does everything on the computer.</add>
				</seg>
				<seg>
					<del seq="20230526083007" type="typo" evidence="1204"><add seq="20230526083006" type="nt" evidence="1203">a</add></del>
					<add seq="20230526083007" type="nt|continue" evidence="1206-1213" ana="2">And I?</add>
				</seg>
				<seg>
					<add seq="20230526083017" type="nt" evidence="1206-1274">I have lost the habit of writing and taking notes on <emph rend="italics">paper</emph>.</add>
				</seg>
				<seg>
					<add seq="20230526083033" type="nt" evidence="1277-1293">My handwriting is </add><mod seq="20230526083139" type="continue" evidence="1362-1371">terrible.</mod>
				</seg>
				<seg>
					<add seq="20230526083143" type="nt" evidence="1374-1433">I am bound to digital writing  forever, there is no way back.</add>
				</seg>
				<seg>
					<add seq="20230526083156" type="nt" evidence="1436-1470">
						<del seq="20230526083213" type="typo" evidence="1492">a</del><add seq="20230526083213" type="typo" evidence="1494">A</add>nd this text is long enough, I l<del seq="20230526083205" type="typo" evidence="1471">o</del></add><add seq="20230526083205" type="nt|continue" evidence="1472-1488">eave it as it is.</add>
				</seg>
				<seg>
					<add seq="20230526083311" type="translocation" evidence="1636">CTRL+S.</add>
				</seg>
				<seg>
					<add seq="20230526083218" type="nt" evidence="1501-1510">Do not <del seq="20230526083221" type="pre-context" evidence="1511-1513">to </del>
					</add>
					<add seq="20230526083222" type="nt|continue" evidence="1514-1537">forget to save the file.</add>
				</seg>
				<seg>
					<del seq="20230526083308" type="translocation" evidence="1628"><add seq="20230526083228" type="nt" evidence="1540-1548">CTRL+S.</add>
					</del>
				</seg>
			</p>
			<p source="sources"> <!-- encode the sources here -->
				<add seq="20230526082504" type="focus" evidence="831">
					<media url="Guardian" mimeType="Internet">
						<desc>Writers' desktops | Books | The Guardian - Google Chrome</desc>
					</media>
				</add>
				<lb/>
				<add seq="20230526082507" type="focus" evidence="834">
					<media url="Guardian" mimeType="Internet">
						<desc>Steven Hall: My desktop | Fiction | The Guardian - Google Chrome</desc>
					</media>
				</add>
				<lb/>
				<add seq="20230526082803" type="focus" evidence="1015">
					<media url="Guardian" mimeType="Internet">
						<desc>Steven Hall: My desktop | Fiction | The Guardian - Google Chrome</desc>
					</media>
				</add>
				<lb/>
				<add seq="20230526082805" type="focus" evidence="1019">
					<media url="Guardian" mimeType="Internet">
						<desc>Writers' desktops | Books | The Guardian - Google Chrome</desc>
					</media>
				</add>
				<lb/>
				<add seq="20230526082816" type="focus" evidence="1027">
					<media url="Guardian" mimeType="Internet">
						<desc>Louise Doughty: My desktop | Fiction | The Guardian - Google Chrome</desc>
					</media>
				</add>
				<lb/>
			</p>
			<p source="notes">
				<note corresp="1">Is this the actual order of the applications in her dock? Why else would she have changed the order on the spur of the moment?</note>
				<note corresp="2">In the next version, this should probably be changed into "And me?".</note>
			</p>
		</body>
	</text>
</TEI>
```

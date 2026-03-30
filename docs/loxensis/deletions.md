# Deletions

Deletions `<del>`

## Attributes

All the attributes listed below are **obligatory** when using `<del>` elements.

| Attribute | Value | Description |
| :--- | :--- | :--- |
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp of the modification in the text |
| `@type` | | The `@type` attribute indicates the type of the addition |
| | `type="pre-context"` | Indicates a deletion that was made *before* the sentence was finished |
| | `type="context"` | Indicates a deletion that was made after the sentence was finished |
| | `type="typo"` | Indicates that the deletion was triggered by a typo |
| | `type="translocation"` | Indicates that the deletion was part of a relocation of the text segment |
| | `type="previousType\|continue"` | Indicates that the deletion was interrupted by an immediate revision, without changing the cursor location, and is now continued |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### `@seq`

> The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

You need to remove the colon's from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss` (see Example 1).

Note that is it important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

There are **4** different addition types: typo related deletions, pre-contextual deletions, contextual deletions, and deletions related to a translocation.

#### Typo related deletion

`<del type="typo">`: A large number of revisions in digital writing occur as a result of typographical errors. Within the scope of genetic criticism, such "typos" are not the most meaningful entities because they do not immediately affect the meaning of the text. Yet, the revision of typographical errors can also break the flow in writing and therefore influence the writing process. In order to be able to distinguish between revisions and typos, every typo is encoded with `@type="typo"`.

There are two ways typos can be corrected:

1. immediately using the backspace-key: in this case, only a typo-related deletion occurs, after which the author continues writing.
2. at a later moment: in this case, both a deletion and an addition occur. The deletion of the wrongly typed character and the addition of the correct one. This is when the `<add type="typo">` is used (see also Additions).

In Example 1, the writer first wrote "he says: ", but she of course wanted to start the sentence with a capital 'H'. She thus went back to the start of the sentence to first delete the 'h', and then type the 'H'. The deleting of the 'h' is, of course, the typo related deletion.

##### Example 1

```xml
<add seq="20230526082627" type="nt" evidence="922-931">
  <del seq="20230526082633" type="typo" evidence="935">h</del>
  <add seq="20230526082633" type="typo" evidence="937">H</add>
  e says:
</add>
```

In Example 2, the writer was producing a new sentence when she made a typo - "On the digital aper" - she missed the 'p'-key. She immediately noticed this, deleted "aper" - which is thus the typo related deletion - and continued writing (now she did press the 'p').

##### Example 2

```xml
<add seq="20230526082203" type="nt" evidence="380-398">On the digital
  <del seq="20230526082210" type="typo" evidence="399-402">aper</del>
</add>
<add seq="20230526082211" type="nt|continue" evidence="403-409">paper</add>
```

#### Pre-contextual deletion

`<del type="pre-context">`: Pre-contextual deletions occur during writing, specifically, before a sentence has been completed. Most pre-contextual **revisions** are made as the writer decides that something needs to be adjusted in the moment of writing, and are therefore mostly represented as 'pre-contextual deletions'. In this case the writer immediately presses the backspace key to delete the just written text and then continues writing. The cursor is not relocated.

In Example 3, the writer wrote "Does it make writing easier, or is this you". She then deleted "you", and continued writing "just a myth?"

##### Example 3

```xml
<add seq="20230526082358" type="nt" evidence="700-742">Does it make writing easier, or is this
  <del seq="20230526082408" type="pre-context" evidence="743-745">you</del>
</add>
<add seq="20230526082409" type="nt|continue" evidence="746-758">just a myth?</add>
```

#### Contextual deletion

`<del type="context">`: Contextual revisions, as opposed to pre-contextual revisions, are those revisions that are made in the text that has already been written. In the case of contextual additions, the writer relocates the cursor to insert text in already written text, or it is part of a substitution (contextual deletion and contextual addition). Contextual additions can take place at any point after writing the text in question, such as immediately after the production of the sentence, or at a later stage.

In Example 4, the writer had previously written the sentence "Louise Doughty always thought that she needed the physical connection to the paper." The word "physical" was already added later (`<add type="context"`). After a short while, she returned to the sentence again to delete "thought", which is thus the contextual deletion (`<del type="context">`), and to replace it with "used to think that" (`<add type="context">`).

##### Example 4

```xml
<add seq="20230526082847" type="nt" evidence="1043-1061">Louise Dought
  <del seq="20230526082854" type="typo" evidence="1062">l</del>
</add>
<add seq="20230526082854" type="nt|continue" evidence="1063-1085">y always
  <del seq="20230526083119" type="context" evidence="1336">thought </del>
  <add seq="20230526083121" type="context" evidence="1338-1358">used to think that </add>
  she
  <del seq="20230526082904" type="typo" evidence="1086-1088">e n</del>
</add>
<add seq="20230526082905" type="nt|continue" evidence="1089-1124"> needed the
  <add seq="20230526082952" type="context" evidence="1189-1197">physical </add>
  connection to the paper.
</add>
```

#### Translocation related deletion

`<del type="translocation">`: Digital writing allows for easy relocating text elements, for example by using 'CTRL X' and 'CTRL V'. In the basis, the translocation is just a deletion of text in one location in the text, and adding it again at another location. To allow these movements of text to be included in the encoding, and differentiated from other revision types, the translocations are encoded using `@type="translocation"`, for both the deletion and the addition.

In Example 5, the writer relocated the short sentence "CTRL+S." The deletion of this sentence is encoded with `<del type="translocation">`.

##### Example 5

```xml
<seg>
  <add seq="20230526083311" type="translocation" evidence="1636">CTRL+S.</add>
</seg>
<seg>
  <add seq="20230526083218" type="nt" evidence="1501-1510">Do not
    <del seq="20230526083221" type="pre-context" evidence="1511-1513">to </del>
  </add>
  <add seq="20230526083222" type="nt|continue" evidence="1514-1537">forget to save the file.</add>
</seg>
<seg>
  <del seq="20230526083308" type="translocation" evidence="1628">
    <add seq="20230526083228" type="nt" evidence="1540-1548">CTRL+S.</add>
  </del>
</seg>
```

##### Example 6

```xml
<add seq="20230526082703" type="source" evidence="971">Longhand isn't well suited to my way of writing. I tend to end up with dozens of pages of crossings-out and margin scribbles just to find one good paragraph, and it's easy to lose your train of thought, working like that.</add>
```

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

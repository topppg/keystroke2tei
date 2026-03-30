# Returns to Leading Edge

Returns to the leading edge `<mod>`

**Table of contents**

- [Attributes](#attributes)
  - [`@seq`](#seq)
  - [`@type`](#type)
  - [`@evidence`](#evidence)

## Attributes

| Attribute | Value | Description |
| :--- | :--- | :--- |
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp of the modification in the text |
| `@type` | | The `@type` attribute indicates the type of the modification |
| | `type="continue"` | Indicates the return to the leading edge of the sentence |
| | `type="continue\|continue"` | Indicates that the continuation was interrupted by an immediate revision, without changing the cursor location, and is now continued |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the writing action was made. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

> **Warning:** You need to remove the colon's from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss` (see Example 1).

Note that is it important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

It occurs that sentences are not finished before modifications are performed elsewhere in the text. This can be described as 'returns to the leading edge'. In the definition formulated by Lindgren et al. (2019)[^1], the leading edge is located "typically at the end of the text produced so far, but can also occur at the end of insertions within previously written text where a writer inserts new ideas (not only revises form)" (347). When the author returns to the sentence to finish it and starts to create new meaning there after a modification elsewhere in the text, this finishing of the sentence would not be an addition. Therefore, to distinguish these returns to the leading edge from 'regular' additions, these actions are classified with `<mod type="continue">`.

In Example 1, the writer started to write a new sentence: "My handwriting is". Then she stopped, to make modifications in other locations in the text (italicising some words, replacing "thought" with "used to think that", see Example General Analysis), after which she returned to the unfinished sentence to finish it by writing "terrible". The return to the unfinished sentence - the leading edge of this sentence - is encoded with `<mod type="continue">` element.

#### Example 1

```xml
<seg><add seq="20230526083033" type="nt" evidence="1277-1293">My handwriting is </add><mod seq="20230526083139" type="continue" evidence="1362-1371">terrible.</mod></seg>
```

In Example 2, the writer began writing the new sentence with "Microsoft Word, Notion, ", then she changed the cursor location to write a new start of the sentence ("Finder, Calendar, Safari, Microsoft Outlook,"; a pre-contextual addition, interrupted by an immediately corrected typo). After this pre-contextual addition, she moved the cursor back to the end of the still unfinished sentence, to continue writing it: "Scrivener, ado". This is encoded with `<mod type="continue">`. She made a typo (not capitalising A) and immediately corrected it. The continuation of finishing the sentence after the correction is therefore encoded with `<mod type="continue|continue">`.

#### Example 2

```xml
<seg><add seq="20230526082028" type="pre-context" evidence="185-197">Finder, Cal<del seq="20230526082033" type="typo" evidence="198">a</del></add><add seq="20230526082033" type="pre-context|continue" evidence="199-235">endar, Safari, Microsoft Oulook, </add><add seq="20230526082014" type="nt" evidence="153-177">Microsoft Word, Notion, </add><mod seq="20230529082051" type="continue" evidence="240-250">Scrivener, <del seq="20230526082058" type="typo" evidence="255-257">ado</del></mod><mod seq="20230526082059" type="continue|continue" evidence="259-311">Adobe Acrobat Reader, the Downloads folder, Bin.</mod></seg>
```

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

> **Warning:** The number in every `@evidence` needs the be **unique**, each encoded writing operation will be identified using this number.

---

[^1]: [Lindgren, Eva, Asbjorg Westum, Hanna Outakoski, and Kirk P.H. Sullivan. 2019. 'Revising at the Leading Edge: Shaping Ideas or Clearing up Noise'. In Observing Writing, edited by Eva Lindgren and Kirk P.H. Sullivan, 346-65. Leiden: Brill.](https://doi.org/10.1163/9789004392526_017)

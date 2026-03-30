# Sources

## Sources `<media>`

The online sources, websites, etc. that the writer visited during the writing process, and that were logged with Inputlog, are encoded in a separate `<p>` element: `<p source="sources">`.

When a writer visited online sources during the writing process, these can be encoded using the `<media>` element. According to the TEI Guidelines, the `<media>` element requires the `<desc>` element as a child, in which the description of the source can be given, e.g. the title of the website or the application.

## Attributes for `<media>`

The consulted sources should be encoded in the `<media>` element.

| Attribute | Value | Description |
| :--- | :--- | :--- |
| `@url` | `url="Guardian"` | The `@url` attribute gives the specific url or the name of the website that was visited |
| `@mimeType` | | The `@type` attribute indicates the type of the source |

### `@url`

The `@url` indicates the specific url of the website that was visited, if given. If not, it gives the name of the website.

### `@mimeType`

The `@mimeType` attribute indicates the type of the source, such as an Internet-page or a local application. You could also opt to adhere to the TEI Guidelines by listing one from the Multipurpose Internet Mail Extensions (MIME) Media Type system. This typology of media is defined by the Internet Engineering Task Force in RFC 2046 (see [TEI Guidelines](https://www.tei-c.org/release/doc/tei-p5-doc/en/html/ref-att.internetMedia.html)). The [list of types](https://www.iana.org/assignments/media-types/media-types.xhtml) is maintained by the Internet Assigned Numbers Authority (IANA).

Example 1 shows how the sources should be encoded. During the writing process, the writer visited the webpage "Writer's desktops" from *The Guardian*, which led her to the online article about the desktop from the writer Steven Hall.

#### Example 1

```xml
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
```

## Attributes for `<add>` for the sources

The `<media>` element should be surrounded by an `<add>` element, to indicate the moment on which the source was consulted. This would allow it to be included in the replay function offered in Keystroke Loxensis.

| Attribute | Value | Description |
| :--- | :--- | :--- |
| `@seq` | `seq="yyyymmddhhminminsecsec"` | The `@seq` attribute gives the value of the timestamp of the when the digital in the text |
| `@type` | | The `@type` attribute indicates the type of the addition |
| | `type="focus"` | Indicates that text was added by pasting directly from a digital source (e.g. website, other digital document) |
| `@evidence` | `evidence="###"` | The `@evidence` attribute gives the value of the #id in the General Analysis of Inputlog |

### `@seq`

The value of the `@seq` attribute should be the time indication of when the digital source was consulted. A good option is to take the time given in the General Analysis in the 'Event StartClock'-column, in the format `hhmmss`.

> **Warning:** You need to remove the colons from the time, otherwise the TEI-XML encoding will not be valid!

- When encoding single-session writing processes, you can use just the time for the 'Event StartClock'.
- When encoding multi-session writing processes, however, you can opt to encode the date of the writing session as well, in the format `yyyymmddhhmmss`.

Note that it is important that the value of the `@seq` attribute allows for listing the writing actions chronologically. When multiple writing actions are made at the same time, the order of the actions is determined by the order in which they appear in the XML tree. If another order is preferred, then change the time by adding one second to the writing action that should appear later.

### `@type`

The value of the `@type` attribute should be `"source"` when you add the `<add>` element for the moment a source was consulted.

### `@evidence`

The value of the `@evidence` attribute should (at least) be the number of the 'Event id' of the first pressed key of the writing action.

> **Warning:** The number in every `@evidence` needs to be **unique**, each encoded writing operation will be identified using this number.

# The Start Files

## What do you need for the encoding?

1. The most fine-grained analysis from the used keystroke logging tool, e.g. the General Analysis from [Inputlog](https://www.inputlog.net), or the Session Log from [GGXLog](https://www.ggxlog.net/index.php).
2. An XML editor.
3. Use the 'Start file' below as your basic template

## Start file

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

# Example Encoding

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

# Code tables

The category and funding code tables change between extracts and are kept only in these two files.

fund_codes.pdf is a one-page PDF. It is a PDF file as ISO 32000-1 defines it. Its page content stream is compressed with the Flate (zlib) filter. After its title line, every text line of the page has the form `<funding code> = <segment>`.

cat_codes.docx is a Word document. It is a WordprocessingML document as ECMA-376 defines it. Its body holds one table whose header row reads `code` and `category`; every further row gives a category code and its category name.

A report writes the segment and category names exactly as these tables give them.

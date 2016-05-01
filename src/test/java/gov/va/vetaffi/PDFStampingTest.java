package gov.va.vetaffi;

import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.HashMap;

import static org.junit.Assert.*;

public class PDFStampingTest {

    @Rule
    public TemporaryFolder TMP = new TemporaryFolder();

    @Test
    public void testStampPdfWithCheckAndText() throws Exception {
        InputStream pdfTemplate =
                PDFStreamingOutput.class.getClassLoader().getResourceAsStream("forms/VBA-21-4502-ARE.pdf");
        File tmpFile = TMP.newFile();

        HashMap<String, String> idMap = Maps.newHashMap();
        idMap.put("Army", "ARMY[0]");
        PDFStamping.stampPdf(pdfTemplate,
                Lists.newArrayList(
                        new PDFField("first_name", "jeff"),
                        new PDFField("branch", "Army")
                ),
                Lists.newArrayList(
                        new PDFFieldLocator("namefirst1[0]", "first_name", 0, null, null, null),
                        new PDFFieldLocator(null, "branch", 0, idMap, null, null)
                ),
                new FileOutputStream(tmpFile));
    }
}
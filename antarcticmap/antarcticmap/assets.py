import tarfile
import sys
import os
import shutil
import urllib.request
from datetime import date, timedelta
from osgeo import gdal
from dagster import asset, AssetExecutionContext, MetadataValue
import rasterio
import matplotlib.pyplot as plt
from rasterio.plot import show

sys.setrecursionlimit(15000)


def yesterday_str():
    yesterday = date.today() - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


@asset(group_name="seaice", compute_kind="seaice data ETL")
def seaice_data_download(context: AssetExecutionContext) -> str:
    os.makedirs("/geodata/source", exist_ok=True)

    """Get the latest sea ice raster data from polarview
    Website: https://www.polarview.aq/
    """
    # get yesterday's date
    yesterday = yesterday_str()

    # if file exists, skip download
    if os.path.exists("/geodata/source/" + yesterday + ".antarctic.tar.gz"):
        context.log.info("File exists, skip download")
        return yesterday

    # download the file
    url = "https://www.polarview.aq/images/27_AMSR2/{}/{}.antarctic.tar.gz"
    url = url.format(yesterday, yesterday)
    saved_name = "{}.antarctic.tar.gz".format(yesterday)
    urllib.request.urlretrieve(url, "/geodata/source/" + saved_name)
    context.log.info("Downloaded {}".format(saved_name))
    return yesterday


@asset(group_name="seaice", compute_kind="seaice data ETL")
def extract_geotif(context: AssetExecutionContext, seaice_data_download: str) -> str:
    """Extract the geotif from the tar.gz file"""
    os.makedirs("/geodata/seaice", exist_ok=True)

    # extract the geotif file
    file = seaice_data_download
    tar = tarfile.open("/geodata/source/" + file + ".antarctic.tar.gz", "r:gz")
    tif_name = "{}.antarctic.tif".format(file)
    member = "data/polarview/27_AMSR2/{}/{}".format(file, tif_name)

    # Just need the geotif file
    new_path = os.path.join("/geodata", "seaice")
    tar.extract(member, path=new_path)

    # move to the root of the folder
    shutil.move(
        os.path.join(new_path, member),
        os.path.join(new_path, tif_name),
    )

    # remove useless files, source will be kept for feature engineering
    shutil.rmtree(os.path.join(new_path, "data"))

    context.log.info(
        "file {} (size: {}MB) is ready".format(
            tif_name, os.path.getsize(os.path.join(new_path, tif_name)) / 1000000
        )
    )

    return tif_name


@asset(group_name="seaice", compute_kind="seaice data ETL")
def generate_thumbnail(context: AssetExecutionContext, extract_geotif: str):
    os.makedirs("/geodata/seaice_thumb", exist_ok=True)

    """
    Generate geotiff by GDAL, using gdal.Translate()
    https://github.com/Jianxuan-Li/antarctic-map/blob/master/geodata/etl_pipeline/sea_ice/etl.py
    """
    seaice_path = os.path.join("/geodata", "seaice")

    tif_file = extract_geotif
    png_file = "{}.antarctic.png".format(tif_file.split(".")[0])

    # Use GDAL translate generate PNG image, only worked with color table
    gdal.Translate(
        os.path.join("/geodata", "seaice_thumb", png_file),
        os.path.join(seaice_path, tif_file),
        format="PNG",
        noData=0,
    )

    # Embed the image into Markdown content for quick view
    # temporary solution, need to be changed in production, e.g. upload to S3
    png_url = "http://localhost:8000/geodata/seaice_thumb/{}".format(png_file)

    mdcontent = "![seaice]({})".format(png_url)
    context.add_output_metadata({"Thumbnail": MetadataValue.md(mdcontent)})

    return png_file


@asset(group_name="seaice", compute_kind="seaice data analysis")
def analysis(
    context: AssetExecutionContext, extract_geotif: str, generate_thumbnail: str
):
    """
    Analysis the sea ice data
    Draw a approximately potential unstable area
    """

    raster_file = rasterio.open(os.path.join("/geodata", "seaice", extract_geotif))
    raster = raster_file.read(1)

    # analysis
    m, n = len(raster), len(raster[0])

    def dfs(row, col, val):
        nonlocal m, n
        if (row, col) in seen:
            return
        seen.add((row, col))

        raster[row][col] = val

        for r, c in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nr, nc = row + r, col + c
            if (
                nr < 0
                or nc < 0
                or nr >= m
                or nc >= n
                or raster[nr][nc] == 0
                or raster[nr][nc] == 120
                or raster[nr][nc] == val
                or raster[nr][nc] > 80
                or (nr, nc) in seen
            ):
                continue

            dfs(nr, nc, val)

    seen = set()
    danger_val = 255
    for x in range(m):
        for y in range(n):
            if (
                raster[x][y] == 0
                or raster[x][y] == 120
                or raster[x][y] > 80
                or raster[x][y] == danger_val
                or (x, y) in seen
            ):
                continue
            dfs(x, y, danger_val)

    # rewrite colormap
    f_colormap = raster_file.colormap(1)
    f_colormap[255] = (255, 0, 0, 255)
    analyzed_file = "{}.analysis.tif".format(extract_geotif.split(".")[0])
    raster_file2 = os.path.join("/geodata", "seaice", analyzed_file)

    # save the analysis result to a new file, band 1
    with rasterio.open(raster_file2, "w", **raster_file.meta) as dst:
        dst.write(raster, indexes=1)
        dst.write_colormap(1, f_colormap)

    context.log.info("Analysis done")

    # generate thumbnail
    gdal.Translate(
        os.path.join("/geodata", "seaice_thumb", analyzed_file + ".png"),
        raster_file2,
        format="PNG",
        noData=0,
    )

    png_url = "http://localhost:8000/geodata/seaice_thumb/{}".format(generate_thumbnail)
    png_url_ana = "http://localhost:8000/geodata/seaice_thumb/{}".format(
        analyzed_file + ".png"
    )

    mdcontent = "![seaice]({})\r\n![seaice_analysis]({})".format(png_url, png_url_ana)
    context.add_output_metadata({"Thumbnail": MetadataValue.md(mdcontent)})

    return analyzed_file


@asset(group_name="seaice", compute_kind="seaice data analysis")
def report(context: AssetExecutionContext, analysis: str, extract_geotif: str):
    """
    Generate a report for the sea ice data
    """
    # read original raster file
    o_raster = rasterio.open(os.path.join("/geodata", "seaice", extract_geotif)).read(1)

    # read analysis raster file
    raster = rasterio.open(os.path.join("/geodata", "seaice", analysis)).read(1)

    _, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    show(raster, contour=True, contour_label_kws={}, ax=ax2)
    ax1.imshow(o_raster, cmap="BrBG")

    # save the report
    report_file = "{}.report.png".format(analysis.split(".")[0])
    plt.savefig(os.path.join("/geodata", "seaice_thumb", report_file))

    # write the report to the metadata
    png_url = "http://localhost:8000/geodata/seaice_thumb/{}".format(report_file)
    mdcontent = "![seaice_report]({})".format(png_url)
    context.add_output_metadata({"Thumbnail": MetadataValue.md(mdcontent)})

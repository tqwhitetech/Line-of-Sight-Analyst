# coding=utf-8
import arcpy

import functions_validation as fv
import functions_visibility as visibility
from los import functions_arcmap


class ExtractLocalHorizons(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Extraction of Local Horizons"
        self.description = "A tool for extraction of local horizons from lines of sight."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Lines of Sight",
            name="in_los",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["Polyline"]

        param1 = arcpy.Parameter(
            displayName="ID observer",
            name="in_id_observer",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #param1.filter.list = ["Integer"]
        #param1.parameterDependencies = [param0.name]
        param1.enabled = 0

        param2 = arcpy.Parameter(
            displayName="Observer points offset",
            name="in_observer_offset",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #param2.filter.list = ["Double"]
        #param2.parameterDependencies = [param0.name]
        param2.enabled = 0

        param3 = arcpy.Parameter(
            displayName="ID target",
            name="in_id_target",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #param3.filter.list = ["Integer"]
        #param3.parameterDependencies = [param0.name]
        param3.enabled = 0

        param4 = arcpy.Parameter(
            displayName="Target points offset",
            name="in_target_offset",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #param4.filter.list = ["Double"]
        #param4.parameterDependencies = [param0.name]
        param4.enabled = 0

        param5 = arcpy.Parameter(
            displayName="Output feature layer",
            name="in_output_layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="output")

        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        fv.enableParamIfLine(parameters, 0, 1)
        fv.enableParamIfLine(parameters, 0, 2)
        fv.enableParamIfLine(parameters, 0, 3)
        fv.enableParamIfLine(parameters, 0, 4)

        if not parameters[5].value:
            parameters[5].value = str(arcpy.env.workspace) + "\\Local_Horizons"

        if parameters[0].value:
            fv.fillParamaterWithFieldTypeAndDefaultFieldIfExists(parameters, 1, parameters[0].valueAsText,
                                                           "SmallInteger", "OID_OBSERV")
            fv.fillParamaterWithFieldTypeAndDefaultFieldIfExists(parameters, 2, parameters[0].valueAsText,
                                                           "Double", "observ_offset")
            fv.fillParamaterWithFieldTypeAndDefaultFieldIfExists(parameters, 2, parameters[0].valueAsText,
                                                           "SmallInteger", "OID_TARGET")
            fv.fillParamaterWithFieldTypeAndDefaultFieldIfExists(parameters, 2, parameters[0].valueAsText,
                                                           "Double", "target_offset")
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        fv.checkProjected(parameters, 0)

        if parameters[0].value:
            message = "The input layer does have fields typical for Global Sight Line. This analysis should be performed on " \
                      "Local Sight Lines. Are you sure you want to proceed?"
            fieldnames = [field.name for field in arcpy.ListFields(parameters[0].value)]

            if "target_x" in fieldnames and "target_y" in fieldnames:
                parameters[1].setWarningMessage(message)
                parameters[3].setWarningMessage(message)
            else:
                parameters[1].clearMessage()
                parameters[3].clearMessage()
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        visibility_lines = parameters[0].valueAsText
        id_observer_field = parameters[1].valueAsText
        observer_offset_field = parameters[2].valueAsText
        id_target_field = parameters[3].valueAsText
        target_offset_field = parameters[4].valueAsText
        horizons = parameters[5].valueAsText

        workspace = fv.getPath(horizons)

        file_name = horizons.replace(workspace + "\\", "")

        arcpy.CreateFeatureclass_management(workspace, file_name, "POINT", has_z="ENABLED",
                                            spatial_reference=arcpy.Describe(visibility_lines).spatialReference)

        field_list = [id_observer_field, id_target_field, "Elevation", "Hor_Type", "Hide_Tar", "ViewAngle",
                      "AngleDiff_H", "Dist_Observ", "OID_LoS"]

        self.prepareDataColumns(horizons, field_list, id_observer_field, id_target_field)

        arcpy.AddMessage("\t Determination of horizons started...")

        insert_cursor = arcpy.da.InsertCursor(horizons, ["SHAPE@"] + field_list)

        number_of_LoS = int(arcpy.GetCount_management(visibility_lines).getOutput(0))
        arcpy.SetProgressor("step", "Analyzing " + str(number_of_LoS) + " lines of sight...", 0, number_of_LoS, 1)

        with arcpy.da.SearchCursor(visibility_lines,
                                   ["OBJECTID", "SHAPE@", id_observer_field, id_target_field, observer_offset_field,
                                    target_offset_field]) as cursor:
            for row in cursor:

                points = []
                wkt = row[1].WKT.replace("))", "").replace(" ((", "").replace("MULTILINESTRING ", "") \
                    .replace("ZM", "").replace("Z", "").replace("), (", ", ")

                poi = wkt.split(", ")
                # get coordinates of first point for distance calculation
                start_point_x = float(poi[0].split(" ")[0])
                start_point_y = float(poi[0].split(" ")[1])
                observer_elev = float(poi[0].split(" ")[2]) + float(row[4])
                # for every point do this
                for i in range(0, len(poi)):
                    parts = poi[i].split(" ")
                    x = float(parts[0])
                    y = float(parts[1])
                    z = float(parts[2])
                    dist = visibility.distance(x, y, start_point_x, start_point_y)
                    if i == 0:
                        points.append([x, y, 0, observer_elev, -90])
                    elif i == len(poi) - 1:
                        points.append(
                            [x, y, dist, z + float(row[5]), visibility.angle(dist, z + float(row[5]) - observer_elev)])
                    else:
                        points.append([x, y, dist, z, visibility.angle(dist, z - observer_elev)])

                results = visibility.findLocalHorizons(points)

                point = arcpy.Point()

                for i in range(0, len(results)):
                    hor_type = 0
                    point.X = results[i][0]
                    point.Y = results[i][1]
                    point.Z = results[i][3]
                    ptGeometry = arcpy.PointGeometry(point)
                    if i == len(results) - 1:
                        hor_type = 1

                    insert_cursor.insertRow([ptGeometry, row[2], row[3], results[i][3], hor_type,
                                             results[i][5], results[i][4], results[i][6], results[i][2], row[0]])

                arcpy.SetProgressorPosition()

        arcpy.ResetProgressor()
        arcpy.AddMessage("\t Determination of horizons sucessfuly ended.")

        functions_arcmap.addLayer(horizons)
        return

    def prepareDataColumns(self, data, columns_list, id_observer_field, id_target_field):
        fieldObjList = arcpy.ListFields(data)
        fieldNameList = []
        for field in fieldObjList:
            if not field.required:
                fieldNameList.append(field.name)

        for field_vis in columns_list:
            if any(field_vis in s for s in fieldNameList):
                arcpy.DeleteField_management(data, field_vis)
            if field_vis == "OID_LoS" or field_vis == "Hor_Type" or field_vis == "Hide_Tar" \
                    or field_vis == id_observer_field  or field_vis == id_target_field:
                arcpy.AddField_management(data, field_vis, "SHORT")
            else:
                arcpy.AddField_management(data, field_vis, "DOUBLE")
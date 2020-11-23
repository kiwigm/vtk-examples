#!/usr/bin/env python

from pathlib import Path

import vtk


def main(data_folder, tissues, view):
    colors = vtk.vtkNamedColors()

    # Setup render window, renderer, and interactor.
    renderer = vtk.vtkRenderer()
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window_interactor = vtk.vtkRenderWindowInteractor()
    render_window_interactor.SetRenderWindow(render_window)

    tm = create_tissue_map()
    path = Path(data_folder)
    color_lut = create_frog_lut()
    res = ['Using the following tissues:']
    for tissue in tissues:
        if path.is_dir():
            source = path.joinpath(tissue).with_suffix('.vtk')
            if not source.is_file():
                s = 'The file: {:s} does not exist.'.format(str(source))
                print(s)
                continue
        actor = create_frog_actor(str(source), tissue, tm[tissue][1])
        actor.GetProperty().SetOpacity(tm[tissue][2])
        actor.GetProperty().SetDiffuseColor(color_lut.GetTableValue(tm[tissue][0])[:3])
        actor.GetProperty().SetSpecular(0.2)
        actor.GetProperty().SetSpecularPower(10)
        renderer.AddActor(actor)
        res.append('{:>11s}, label: {:2d}'.format(tissue, tm[tissue][0]))

    print('\n'.join(res))
    render_window.SetSize(640, 640)
    render_window.SetWindowName('Froggie')

    renderer.SetBackground(colors.GetColor3d('LightSteelBlue'))

    #  Initial view (looking down on the dorsal surface).
    renderer.GetActiveCamera().SetViewUp(0, -1, 0)
    renderer.GetActiveCamera().Roll(90)
    renderer.ResetCamera()

    #  Final view
    if view:
        if view == 'a':
            # Figs 12-9a and 12-9b in the VTK Textbook
            camera = renderer.GetActiveCamera()
            camera.SetPosition(-599.880035, 548.906952, 313.670289)
            camera.SetFocalPoint(-8.376500, 40.691664, -156.007163)
            camera.SetViewUp(0.294699, -0.440638, 0.847933)
            camera.SetDistance(910.360434)
            camera.SetClippingRange(231.699387, 1758.550290)
        elif view == 'c':
            # Figs 12-9c in the VTK Textbook
            camera = renderer.GetActiveCamera()
            camera.SetPosition(-206.616664, 182.524078, 87.589931)
            camera.SetFocalPoint(-5.721571, -0.074326, -97.940837)
            camera.SetViewUp(0.300335, -0.496855, 0.814208)
            camera.SetDistance(328.820135)
            camera.SetClippingRange(0.810268, 810.268454)
        elif view == 'd':
            # Fig 12-9d in the VTK Textbook
            camera = renderer.GetActiveCamera()
            camera.SetPosition(-40.912047, -65.274764, 588.508700)
            camera.SetFocalPoint(-10.418979, 17.700133, -158.643842)
            camera.SetViewUp(0.741687, -0.669297, -0.044059)
            camera.SetDistance(752.363995)
            camera.SetClippingRange(444.653021, 997.508259)

    render_window.Render()

    axes = vtk.vtkAxesActor()

    widget = vtk.vtkOrientationMarkerWidget()
    rgba = [0.0, 0.0, 0.0, 0.0]
    colors.GetColor("Carrot", rgba)
    widget.SetOutlineColor(rgba[0], rgba[1], rgba[2])
    widget.SetOrientationMarker(axes)
    widget.SetInteractor(render_window_interactor)
    widget.SetViewport(0.0, 0.0, 0.2, 0.2)
    widget.SetEnabled(1)
    widget.InteractiveOn()

    render_window_interactor.Start()


def get_program_parameters(argv):
    import argparse
    description = 'Some description.'
    epilogue = '''
    To specify all the tissue at once:
        blood brain brainbin duodenum eye_retna eye_white heart ileum kidney l_intestine liver lung nerve skeleton spleen stomach skin
    You can leave out brainbin.
    
    Fig12-9a:
       blood brain duodenum eye_retna eye_white heart ileum kidney l_intestine liver lung nerve skeleton spleen stomach skin -a
    Fig12-9b:
       blood brain duodenum eye_retna eye_white heart ileum kidney l_intestine liver lung nerve skeleton spleen stomach -a
    Fig12-9c:
       brain duodenum eye_retna eye_white heart ileum kidney l_intestine liver lung nerve spleen stomach -c
    Fig12-9c:
       brain duodenum eye_retna eye_white heart ileum kidney l_intestine liver lung nerve spleen stomach -d
    '''
    parser = argparse.ArgumentParser(description=description, epilog=epilogue,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', action='store_const', dest='view', const='a',
                       help='The view corresponds to Figs 12-9a and 12-9b in the VTK Textbook')
    group.add_argument('-c', action='store_const', dest='view', const='c',
                       help='The view corresponds to Figs 12-9c in the VTK Textbook')
    group.add_argument('-d', action='store_const', dest='view', const='d',
                       help='The view corresponds to Figs 12-9d in the VTK Textbook')
    parser.set_defaults(type=None)

    parser.add_argument('data_folder', help='frog')
    parser.add_argument('tissues', nargs='+', help='List of one or more tissues.')
    args = parser.parse_args()
    return args.data_folder, args.tissues, args.view


class SliceOrder:
    """
    These transformations permute image and other geometric data to maintain proper
     orientation regardless of the acquisition order. After applying these transforms with
    vtkTransformFilter, a view up of 0,-1,0 will result in the body part
    facing the viewer.
    NOTE: some transformations have a -1 scale factor for one of the components.
          To ensure proper polygon orientation and normal direction, you must
          apply the vtkPolyDataNormals filter.

    Naming (the nomenclature is medical):
    si - superior to inferior (top to bottom)
    is - inferior to superior (bottom to top)
    ap - anterior to posterior (front to back)
    pa - posterior to anterior (back to front)
    lr - left to right
    rl - right to left
    """

    def __init__(self):
        self.si_mat = vtk.vtkMatrix4x4()
        self.si_mat.Zero()
        self.si_mat.SetElement(0, 0, 1)
        self.si_mat.SetElement(1, 2, 1)
        self.si_mat.SetElement(2, 1, -1)
        self.si_mat.SetElement(3, 3, 1)

        self.is_mat = vtk.vtkMatrix4x4()
        self.is_mat.Zero()
        self.is_mat.SetElement(0, 0, 1)
        self.is_mat.SetElement(1, 2, -1)
        self.is_mat.SetElement(2, 1, -1)
        self.is_mat.SetElement(3, 3, 1)

        self.lr_mat = vtk.vtkMatrix4x4()
        self.lr_mat.Zero()
        self.lr_mat.SetElement(0, 2, -1)
        self.lr_mat.SetElement(1, 1, -1)
        self.lr_mat.SetElement(2, 0, 1)
        self.lr_mat.SetElement(3, 3, 1)

        self.rl_mat = vtk.vtkMatrix4x4()
        self.rl_mat.Zero()
        self.rl_mat.SetElement(0, 2, 1)
        self.rl_mat.SetElement(1, 1, -1)
        self.rl_mat.SetElement(2, 0, 1)
        self.rl_mat.SetElement(3, 3, 1)

        """
        The previous transforms assume radiological views of the slices (viewed from the feet). other
        modalities such as physical sectioning may view from the head. These transforms modify the original
        with a 180° rotation about y
        """

        self.hf_mat = vtk.vtkMatrix4x4()
        self.hf_mat.Zero()
        self.hf_mat.SetElement(0, 0, -1)
        self.hf_mat.SetElement(1, 1, 1)
        self.hf_mat.SetElement(2, 2, -1)
        self.hf_mat.SetElement(3, 3, 1)

    def s_i(self):
        t = vtk.vtkTransform()
        t.SetMatrix(self.si_mat)
        return t

    def i_s(self):
        t = vtk.vtkTransform()
        t.SetMatrix(self.is_mat)
        return t

    @staticmethod
    def a_p():
        t = vtk.vtkTransform()
        return t.Scale(1, -1, 1)

    @staticmethod
    def p_a():
        t = vtk.vtkTransform()
        return t.Scale(1, -1, -1)

    def l_r(self):
        t = vtk.vtkTransform()
        t.SetMatrix(self.lr_mat)
        t.Update()
        return t

    def r_l(self):
        t = vtk.vtkTransform()
        t.SetMatrix(self.lr_mat)
        return t

    def h_f(self):
        t = vtk.vtkTransform()
        t.SetMatrix(self.hf_mat)
        return t

    def hf_si(self):
        t = vtk.vtkTransform()
        t.Concatenate(self.hf_mat)
        t.Concatenate(self.si_mat)
        return t

    def hf_is(self):
        t = vtk.vtkTransform()
        t.Concatenate(self.hf_mat)
        t.Concatenate(self.is_mat)
        return t

    def hf_ap(self):
        t = vtk.vtkTransform()
        t.Concatenate(self.hf_mat)
        t.Scale(1, -1, 1)
        return t

    def hf_pa(self):
        t = vtk.vtkTransform()
        t.Concatenate(self.hf_mat)
        t.Scale(1, -1, -1)
        return t

    def hf_lr(self):
        t = vtk.vtkTransform()
        t.Concatenate(self.hf_mat)
        t.Concatenate(self.lr_mat)
        return t

    def hf_rl(self):
        t = vtk.vtkTransform()
        t.Concatenate(self.hf_mat)
        t.Concatenate(self.rl_mat)
        return t

    def get(self, order):
        """
        Returns the vtkTransform corresponding to the slice order.
        
        :param order: The slice order
        :return: The vtkTransform to use
        """
        if order == 'si':
            return self.s_i()
        elif order == 'is':
            return self.i_s()
        elif order == 'ap':
            return self.a_p()
        elif order == 'pa':
            return self.p_a()
        elif order == 'lr':
            return self.l_r()
        elif order == 'rl':
            return self.r_l()
        elif order == 'hf':
            return self.h_f()
        elif order == 'hfsi':
            return self.hf_si()
        elif order == 'hfis':
            return self.hf_is()
        elif order == 'hfap':
            return self.hf_ap()
        elif order == 'hfpa':
            return self.hf_pa()
        elif order == 'hflr':
            return self.hf_lr()
        elif order == 'hfrl':
            return self.hf_rl()
        else:
            s = 'No such transform "{:s}" exists.'.format(order)
            raise Exception(s)


def create_frog_lut():
    colors = vtk.vtkNamedColors()

    lut = vtk.vtkLookupTable()
    lut.SetNumberOfColors(17)
    lut.SetTableRange(0, 16)
    lut.Build()

    lut.SetTableValue(0, 0, 0, 0, 0)
    lut.SetTableValue(1, colors.GetColor4d('salmon'))  # blood
    lut.SetTableValue(2, colors.GetColor4d('beige'))  # brain
    lut.SetTableValue(3, colors.GetColor4d('orange'))  # duodenum
    lut.SetTableValue(4, colors.GetColor4d('misty_rose'))  # eye_retina
    lut.SetTableValue(5, colors.GetColor4d('white'))  # eye_white
    lut.SetTableValue(6, colors.GetColor4d('tomato'))  # heart
    lut.SetTableValue(7, colors.GetColor4d('raspberry'))  # ileum
    lut.SetTableValue(8, colors.GetColor4d('banana'))  # kidney
    lut.SetTableValue(9, colors.GetColor4d('peru'))  # l_intestine
    lut.SetTableValue(10, colors.GetColor4d('pink'))  # liver
    lut.SetTableValue(11, colors.GetColor4d('powder_blue'))  # lung
    lut.SetTableValue(12, colors.GetColor4d('carrot'))  # nerve
    lut.SetTableValue(13, colors.GetColor4d('wheat'))  # skeleton
    lut.SetTableValue(14, colors.GetColor4d('violet'))  # spleen
    lut.SetTableValue(15, colors.GetColor4d('plum'))  # stomach
    lut.SetTableValue(16, colors.GetColor4d('LimeGreen'))  # skin

    return lut


def create_tissue_map():
    tiss = dict()
    # key: name of the tissue
    # value: [lut_index, transform, opacity]
    tiss['blood'] = [1, 'is', 1.0]
    tiss['brain'] = [2, 'is', 1.0]
    tiss['brainbin'] = [2, 'is', 1.0]
    tiss['duodenum'] = [3, 'is', 1.0]
    tiss['eye_retna'] = [4, 'is', 1.0]
    tiss['eye_white'] = [5, 'is', 1.0]
    tiss['heart'] = [6, 'is', 1.0]
    tiss['ileum'] = [7, 'is', 1.0]
    tiss['kidney'] = [8, 'is', 1.0]
    tiss['l_intestine'] = [9, 'is', 1.0]
    tiss['liver'] = [10, 'is', 1.0]
    tiss['lung'] = [11, 'is', 1.0]
    tiss['nerve'] = [12, 'is', 1.0]
    tiss['skeleton'] = [13, 'is', 1.0]
    tiss['spleen'] = [14, 'is', 1.0]
    tiss['stomach'] = [15, 'is', 1.0]
    tiss['skin'] = [16, 'hfsi', 0.4]
    return tiss


def create_frog_actor(file_name, tissue, transform):
    so = SliceOrder()

    reader = vtk.vtkPolyDataReader()
    reader.SetFileName(file_name)
    reader.Update()

    trans = so.get(transform)
    if tissue == 'brainbin':
        trans.Scale(1, -1, 1)
        trans.RotateZ(180)
    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputConnection(reader.GetOutputPort())
    tf.SetTransform(trans)
    tf.SetInputConnection(reader.GetOutputPort())

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(tf.GetOutputPort())
    normals.SetFeatureAngle(60.0)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    return actor


if __name__ == '__main__':
    import sys

    data_folder, tissues, view = get_program_parameters(sys.argv)
    main(data_folder, tissues, view)